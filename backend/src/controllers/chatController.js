/**
 * Chat Controller
 * Handles thread and message management
 */
import { v4 as uuidv4 } from 'uuid';
import { database } from '../db/database.js';

/**
 * GET /api/threads
 * Get all threads for the authenticated user
 */
export async function getThreads(req, res) {
    try {
        const userId = req.user.id;

        const threads = await database.getUserThreads(userId);

        // Get message count for each thread
        const threadsWithCounts = await Promise.all(
            threads.map(async (thread) => {
                const messages = await database.getThreadMessages(thread.id);
                return {
                    ...thread,
                    messageCount: messages.length,
                };
            })
        );

        res.json({ threads: threadsWithCounts });

    } catch (error) {
        console.error('[Chat] Error fetching threads:', error);
        res.status(500).json({
            error: 'Failed to fetch threads',
            message: error.message,
        });
    }
}

/**
 * POST /api/threads
 * Create a new thread
 */
export async function createThread(req, res) {
    try {
        const userId = req.user.id;
        const { title } = req.body;

        if (!title) {
            return res.status(400).json({ error: 'Thread title is required' });
        }

        const threadId = uuidv4();
        await database.createThread(threadId, userId, title);

        const thread = await database.getThreadById(threadId);

        res.status(201).json({ thread });

    } catch (error) {
        console.error('[Chat] Error creating thread:', error);
        res.status(500).json({
            error: 'Failed to create thread',
            message: error.message,
        });
    }
}

/**
 * DELETE /api/threads/:threadId
 * Delete a thread (only if it belongs to the user)
 */
export async function deleteThread(req, res) {
    try {
        const userId = req.user.id;
        const { threadId } = req.params;

        // Verify thread belongs to user
        const thread = await database.getThreadById(threadId);

        if (!thread) {
            return res.status(404).json({ error: 'Thread not found' });
        }

        if (thread.user_id !== userId) {
            return res.status(403).json({ error: 'Access denied' });
        }

        await database.deleteThread(threadId);

        console.log(`[Chat] Thread deleted: ${threadId} by user ${userId}`);

        res.json({ success: true, message: 'Thread deleted successfully' });

    } catch (error) {
        console.error('[Chat] Error deleting thread:', error);
        res.status(500).json({
            error: 'Failed to delete thread',
            message: error.message,
        });
    }
}

/**
 * GET /api/threads/:threadId/messages
 * Get all messages for a thread
 */
export async function getThreadMessages(req, res) {
    try {
        const userId = req.user.id;
        const { threadId } = req.params;

        // Verify thread belongs to user
        const thread = await database.getThreadById(threadId);

        if (!thread) {
            return res.status(404).json({ error: 'Thread not found' });
        }

        if (thread.user_id !== userId) {
            return res.status(403).json({ error: 'Access denied' });
        }

        const messages = await database.getThreadMessages(threadId);

        res.json({ messages });

    } catch (error) {
        console.error('[Chat] Error fetching messages:', error);
        res.status(500).json({
            error: 'Failed to fetch messages',
            message: error.message,
        });
    }
}

/**
 * PUT /api/threads/:threadId
 * Update thread title
 */
export async function updateThread(req, res) {
    try {
        const userId = req.user.id;
        const { threadId } = req.params;
        const { title } = req.body;

        if (!title) {
            return res.status(400).json({ error: 'Title is required' });
        }

        // Verify thread belongs to user
        const thread = await database.getThreadById(threadId);

        if (!thread) {
            return res.status(404).json({ error: 'Thread not found' });
        }

        if (thread.user_id !== userId) {
            return res.status(403).json({ error: 'Access denied' });
        }

        await database.updateThread(threadId, title);

        res.json({ success: true, message: 'Thread renamed successfully' });

    } catch (error) {
        console.error('[Chat] Error updating thread:', error);
        res.status(500).json({
            error: 'Failed to update thread',
            message: error.message,
        });
    }
}

/**
 * POST /api/chat
 * Main chat logic: handle thread, save user message, queue RAG job
 */
export async function processChat(req, res) {
    try {
        const { query, threadId } = req.body;
        const userId = req.user.id;

        // Validation
        if (!query || typeof query !== 'string' || query.trim().length === 0) {
            return res.status(400).json({
                error: 'Query is required and must be a non-empty string',
            });
        }

        // Determine thread ID
        let actualThreadId = threadId;

        // If no threadId provided, create new thread
        if (!actualThreadId) {
            actualThreadId = uuidv4();
            const title = generateThreadTitle(query.trim());
            await database.createThread(actualThreadId, userId, title);
            console.log(`[Chat] Created new thread: ${actualThreadId} for user ${userId}`);
        } else {
            console.log(`[Chat] Using existing thread: ${actualThreadId} for user ${userId}`);
            // Verify thread belongs to user
            const thread = await database.getThreadById(actualThreadId);
            if (!thread) {
                return res.status(404).json({ error: 'Thread not found' });
            }
            if (thread.user_id !== userId) {
                return res.status(403).json({ error: 'Access denied to this thread' });
            }
        }

        // Save user message to database
        const userMessageId = uuidv4();
        await database.createMessage(userMessageId, actualThreadId, 'user', query.trim());

        // Import queue and worker abortion logic
        const { addRAGJob } = await import('../queues/rag.queue.js');
        const { abortRAGJobByThreadId } = await import('../workers/rag.worker.js');

        // AUTO-ABORT: If there's an active job for this thread, kill it first
        // This prevents the "Sequential Worker" from being stuck on an old query
        await abortRAGJobByThreadId(actualThreadId);

        const jobId = uuidv4();
        // Add job to queue
        await addRAGJob(query.trim(), jobId, {
            threadId: actualThreadId,
            userId: userId,
        });

        console.log(`[Chat] Job queued: ${jobId}, Thread: ${actualThreadId}`);

        res.status(202).json({
            jobId,
            threadId: actualThreadId,
            status: 'queued',
            message: 'Query submitted successfully. Use Socket.IO to receive updates.',
            timestamp: new Date().toISOString(),
        });

    } catch (error) {
        console.error('[Chat] Error processing chat:', error);
        res.status(500).json({
            error: 'Failed to process chat',
            message: error.message,
        });
    }
}

/**
 * Helper: Generate thread title from first message
 */
export function generateThreadTitle(query) {
    // Take first 50 characters of the query as title
    const title = query.length > 50 ? query.substring(0, 50) + '...' : query;
    return title;
}

export default {
    getThreads,
    createThread,
    deleteThread,
    getThreadMessages,
    processChat,
    updateThread,
    generateThreadTitle,
};
