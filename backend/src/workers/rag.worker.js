/**
 * BullMQ Worker for Processing RAG Jobs
 * 
 * CRITICAL: concurrency = 1 (process jobs sequentially)
 * This prevents overloading the Python RAG service.
 */
import { Worker, Queue } from 'bullmq';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { config } from '../config/config.js';
import { database } from '../db/database.js';

let workerInstance = null;

/**
 * Cleanup stale jobs from previous sessions.
 * We use 'clean' instead of 'obliterate' because 'obliterate' wipes 
 * ALL keys including active locks for other potential worker instances.
 */
async function cleanupStaleJobs(connection) {
  try {
    const queue = new Queue('rag-jobs', { connection });

    console.log('[Worker] 🧹 Cleaning up completed/failed jobs...');
    // Clean old finished jobs
    await queue.clean(0, 0, 'completed');
    await queue.clean(0, 0, 'failed');

    // Clean jobs that have been waiting too long without being picked up (1 hour)
    await queue.clean(3600000, 100, 'wait');

    console.log(`[Worker] ✓ Queue cleanup successful (Safer mode)`);
    await queue.close();
  } catch (err) {
    console.error('[Worker] Queue cleanup error (non-fatal):', err.message);
  }
}

const activeControllers = new Map(); // jobId -> AbortController
const activeThreadJobs = new Map(); // threadId -> jobId

/**
 * Initialize the RAG Worker
 * @param {Server} io - Socket.IO server instance
 */
export async function initializeRAGWorker(io) {
  if (workerInstance) return workerInstance;

  // Redis connection configuration
  const redisConnection = {
    host: config.redis.host,
    port: config.redis.port,
    ...(config.redis.url && config.redis.url !== `redis://${config.redis.host}:${config.redis.port}`
      ? { url: config.redis.url }
      : {}),
  };

  // Clean up stale jobs BEFORE starting worker
  await cleanupStaleJobs(redisConnection);

  // Create Worker with concurrency = 1 (CRITICAL CONSTRAINT)
  workerInstance = new Worker(
    'rag-jobs',
    async (job) => {
      const { query, jobId, threadId, userId } = job.data;
      const startTime = Date.now();
      const startTimeISO = new Date().toISOString();

      // Create AbortController for this job
      const controller = new AbortController();
      activeControllers.set(jobId, controller);
      if (threadId) {
        activeThreadJobs.set(threadId, jobId);
      }

      console.log('='.repeat(50));
      console.log(`[Worker] Processing Job ${jobId}`);
      console.log(`[Worker] User: ${userId || 'N/A'}`);
      console.log(`[Worker] Thread: ${threadId || 'N/A'}`);
      console.log(`[Worker] Started at: ${startTimeISO}`);

      try {
        // Fetch chat history for context if threadId exists
        let chatHistory = [];
        if (threadId) {
          try {
            const messages = await database.getThreadMessages(threadId);
            chatHistory = messages
              .slice(-11, -1) // Last 10 messages before the current one
              .map(m => ({
                role: m.role,
                content: m.content
              }));
          } catch (historyError) {
            console.error(`[Worker] Failed to fetch chat history:`, historyError);
          }
        }

        console.log(`[Worker] Sending request to Python RAG Service...`);
        // Make HTTP request to Python RAG service
        const response = await axios.post(
          `${config.ragService.url}/chat`,
          {
            query,
            chat_history: chatHistory
          },
          {
            timeout: config.ragService.timeout,
            signal: controller.signal, // Connect the abort signal
            headers: { 'Content-Type': 'application/json' },
          }
        );

        const endTime = Date.now();
        const endTimeISO = new Date().toISOString();
        const duration = ((endTime - startTime) / 1000).toFixed(2);
        const answer = response.data.answer;

        // Save assistant response to database if thread still exists
        if (threadId) {
          try {
            // Verify thread still exists (avoids FK constraint errors if user deleted thread while processing)
            const thread = await database.getThreadById(threadId);
            if (!thread) {
              console.warn(`[Worker] ⚠️ Thread ${threadId} was deleted during processing. Skipping DB save.`);
            } else {
              const messageId = uuidv4();
              await database.createMessage(messageId, threadId, 'assistant', answer);
              console.log(`[Worker] Saved assistant response to thread ${threadId}`);
            }
          } catch (dbError) {
            console.error(`[Worker] Failed to save message to database:`, dbError);
          }
        }

        const result = {
          answer,
          decision_trace: response.data.decision_trace || {},
          latency_ms: response.data.latency_ms,
          jobId,
          threadId,
          duration_seconds: duration,
        };

        console.log(`[Worker] ✓ Job ${jobId} completed successfully`);
        console.log(`[Worker] Received response at: ${endTimeISO}`);
        console.log(`[Worker] Duration: ${duration}s`);
        console.log(`[Worker] Python Service Latency: ${response.data.latency_ms.toFixed(2)}ms`);
        console.log('='.repeat(50));

        io.to(jobId).emit('chat_complete', {
          jobId,
          ...result,
          timestamp: endTimeISO,
        });

        return result;

      } catch (error) {
        const endTime = Date.now();
        const endTimeISO = new Date().toISOString();
        const duration = ((endTime - startTime) / 1000).toFixed(2);

        let errorMessage = error.message || 'Unknown error';
        let errorType = 'unknown';

        if (axios.isCancel(error)) {
          errorType = 'aborted';
          errorMessage = 'Job was aborted by the user.';
          console.warn(`[Worker] 🛑 Job ${jobId} was ABORTED`);
        } else if (axios.isAxiosError(error)) {
          if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
            errorType = 'timeout';
            errorMessage = `Request timed out after ${config.ragService.timeout / 1000}s.`;
          } else if (error.code === 'ECONNREFUSED') {
            errorType = 'connection_refused';
            errorMessage = `Python RAG service unreachable at ${config.ragService.url}`;
          }
        }

        console.error(`[Worker] ✗ Job ${jobId} failed - ${errorMessage}`);
        io.to(jobId).emit('chat_error', {
          jobId,
          error: errorMessage,
          errorType,
          timestamp: endTimeISO,
          duration_seconds: duration,
        });

        throw new Error(errorMessage);
      } finally {
        // Always remove the controller when done
        activeControllers.delete(jobId);
        if (threadId && activeThreadJobs.get(threadId) === jobId) {
          activeThreadJobs.delete(threadId);
        }
      }
    },
    {
      connection: redisConnection,
      concurrency: 1,
      lockDuration: 60000, // 60 seconds (defaults to 30s)
    }
  );

  workerInstance.on('completed', (job) => console.log(`[Worker] Job ${job.id} completed`));
  workerInstance.on('failed', (job, err) => console.error(`[Worker] Job ${job?.id} failed:`, err.message));
  workerInstance.on('error', (err) => console.error(`[Worker] Worker error:`, err));
  workerInstance.on('lockRenewalFailed', (jobIds) => console.warn(`[Worker] ⚠️ Lock renewal failed:`, jobIds));

  console.log('✓ RAG Worker initialized');
  console.log(`  Queue: rag-jobs`);
  console.log(`  Concurrency: 1`);
  console.log(`  Stalled Check: DISABLED`);
  console.log(`  Safer Cleanup: ENABLED`);
}

/**
 * Abort a running RAG job
 * @param {string} jobId
 */
export async function abortRAGJob(jobId) {
  const controller = activeControllers.get(jobId);
  if (controller) {
    console.log(`[Worker] 🛑 Aborting job ${jobId}...`);
    controller.abort();
    activeControllers.delete(jobId);
    return true;
  }
  return false;
}

/**
 * Abort any active RAG job for a given thread
 * @param {string} threadId
 */
export async function abortRAGJobByThreadId(threadId) {
  const jobId = activeThreadJobs.get(threadId);
  if (jobId) {
    console.log(`[Worker] 🛑 Auto-aborting previous job ${jobId} for thread ${threadId}...`);
    return await abortRAGJob(jobId);
  }
  return false;
}

export function getWorker() {
  return workerInstance;
}
