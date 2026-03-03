/**
 * BullMQ Queue Setup for RAG Jobs
 */
import { Queue } from 'bullmq';
import { config } from '../config/config.js';

// Redis connection configuration
const redisConnection = {
  host: config.redis.host,
  port: config.redis.port,
  // Use URL if provided, otherwise use host/port
  ...(config.redis.url && config.redis.url !== `redis://${config.redis.host}:${config.redis.port}`
    ? { url: config.redis.url }
    : {}),
};

// Create Queue Instance
export const ragQueue = new Queue('rag-jobs', {
  connection: redisConnection,
  defaultJobOptions: {
    attempts: 2,
    backoff: {
      type: 'exponential',
      delay: 5000,
    },
    removeOnComplete: {
      age: 3600, // Keep completed jobs for 1 hour
      count: 100, // Keep max 100 completed jobs
    },
    removeOnFail: {
      age: 86400, // Keep failed jobs for 24 hours
    },
  },
});

/**
 * Add a RAG job to the queue
 * @param {string} query - User query
 * @param {string} jobId - Unique job identifier
 * @returns {Promise<Job>} BullMQ Job instance
 */
export async function addRAGJob(query, jobId, metadata = {}) {
  const job = await ragQueue.add(
    'process-rag-query',
    {
      query,
      jobId,
      ...metadata,
      timestamp: new Date().toISOString(),
    },
    {
      jobId, // Use custom jobId for tracking
    }
  );

  console.log(`[Queue] Job ${jobId} added to queue. Query: "${query.substring(0, 50)}..."`);
  return job;
}

/**
 * Get job status
 * @param {string} jobId - Job identifier
 * @returns {Promise<Object>} Job state
 */
export async function getJobStatus(jobId) {
  const job = await ragQueue.getJob(jobId);

  if (!job) {
    return { status: 'not_found' };
  }

  const state = await job.getState();
  const progress = job.progress;

  return {
    id: job.id,
    status: state,
    progress,
    data: job.data,
    result: job.returnvalue,
    failedReason: job.failedReason,
  };
}
