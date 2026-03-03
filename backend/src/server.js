/**
 * Main Server Entry Point
 * Express HTTP Server + Socket.IO + BullMQ Integration
 */
import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import cors from 'cors';
import { config } from './config/config.js';
import { setupSocketHandlers } from './sockets/socket.handler.js';
import { chatRoutes } from './routes/chat.routes.js';
import { authRoutes } from './routes/auth.routes.js';
import { initializeRAGWorker } from './workers/rag.worker.js';
import { initializeDatabase } from './db/database.js';

const app = express();
const httpServer = createServer(app);

// Socket.IO Setup
const io = new Server(httpServer, {
  cors: {
    origin: config.cors.origin,
    methods: ['GET', 'POST'],
    credentials: true,
  },
  path: config.socketIO.path,
});

// Middleware
app.use(cors({
  origin: config.cors.origin,
  credentials: true,
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health Check
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'RAG Backend',
    timestamp: new Date().toISOString(),
  });
});

// Auth Routes (no authentication required)
app.use('/api', authRoutes);

// Chat Routes (authentication required for most endpoints)
app.use('/api', chatRoutes(io));

// Socket.IO Handlers
setupSocketHandlers(io);

// Initialize Database and Worker
async function startServer() {
  try {
    // Initialize database first
    await initializeDatabase();

    // Initialize Worker (must be after Socket.IO setup)
    await initializeRAGWorker(io);

    // Error Handling Middleware
    app.use((err, req, res, next) => {
      console.error('Error:', err);
      res.status(err.status || 500).json({
        error: err.message || 'Internal Server Error',
      });
    });

    // Start Server
    const PORT = config.port;
    httpServer.listen(PORT, () => {
      console.log('='.repeat(50));
      console.log(`🚀 RAG Backend Server Started`);
      console.log(`   Environment: ${config.nodeEnv}`);
      console.log(`   HTTP Port: ${PORT}`);
      console.log(`   Socket.IO Path: ${config.socketIO.path}`);
      console.log(`   Redis: ${config.redis.url}`);
      console.log(`   Python RAG Service: ${config.ragService.url}`);
      console.log(`   CORS Origin: ${config.cors.origin}`);
      console.log('='.repeat(50));
    });

    // Graceful Shutdown — must close Worker to prevent zombie processes
    const shutdown = async (signal) => {
      console.log(`${signal} received, shutting down gracefully...`);

      // Force exit after 5 seconds if graceful shutdown hangs
      const forceTimeout = setTimeout(() => {
        console.error('Graceful shutdown timed out, forcing exit...');
        process.exit(1);
      }, 5000);
      forceTimeout.unref();

      try {
        // Close BullMQ Worker FIRST (stops lock timers)
        const { getWorker } = await import('./workers/rag.worker.js');
        const worker = getWorker();
        if (worker) {
          console.log('Closing BullMQ Worker...');
          await worker.close();
          console.log('BullMQ Worker closed');
        }
      } catch (e) {
        console.error('Error closing worker:', e.message);
      }

      httpServer.close(() => {
        console.log('HTTP server closed');
        process.exit(0);
      });
    };

    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT', () => shutdown('SIGINT'));
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
