/**
 * Chat Routes
 * 
 * POST /api/chat - Submit a query and get jobId immediately
 * GET /api/job/:jobId - Get job status (optional, Socket.IO is primary)
 * GET /api/threads - Get all threads for authenticated user
 * POST /api/threads - Create a new thread
 * DELETE /api/threads/:threadId - Delete a thread
 * GET /api/threads/:threadId/messages - Get messages for a thread
 */
import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { addRAGJob, getJobStatus } from '../queues/rag.queue.js';
import { authenticateToken } from '../middleware/authMiddleware.js';
import {
  getThreads,
  createThread,
  deleteThread,
  getThreadMessages,
  processChat,
  updateThread,
  generateThreadTitle,
} from '../controllers/chatController.js';
import { database } from '../db/database.js';

export function chatRoutes(io) {
  const router = express.Router();

  /**
   * GET /api/threads
   * Get all threads for authenticated user
   */
  router.get('/threads', authenticateToken, getThreads);

  /**
   * POST /api/threads
   * Create a new thread
   */
  router.post('/threads', authenticateToken, createThread);

  /**
   * DELETE /api/threads/:threadId
   * Delete a thread
   */
  router.delete('/threads/:threadId', authenticateToken, deleteThread);

  /**
   * PUT /api/threads/:threadId
   * Update a thread's title
   */
  router.put('/threads/:threadId', authenticateToken, updateThread);

  /**
   * GET /api/threads/:threadId/messages
   * Get messages for a thread
   */
  router.get('/threads/:threadId/messages', authenticateToken, getThreadMessages);

  /**
   * POST /api/chat
   * Submit a RAG query (now with thread support)
   */
  router.post('/chat', authenticateToken, processChat);

  /**
   * GET /api/job/:jobId
   * Get job status (optional endpoint, Socket.IO is primary)
   */
  router.get('/job/:jobId', async (req, res) => {
    try {
      const { jobId } = req.params;

      if (!jobId) {
        return res.status(400).json({
          error: 'jobId is required',
        });
      }

      const status = await getJobStatus(jobId);

      if (status.status === 'not_found') {
        return res.status(404).json({
          error: 'Job not found',
          jobId,
        });
      }

      res.json({
        jobId,
        ...status,
      });

    } catch (error) {
      console.error('[API] Error getting job status:', error);
      res.status(500).json({
        error: 'Failed to get job status',
        message: error.message,
      });
    }
  });

  return router;
}
