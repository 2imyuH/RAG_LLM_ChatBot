import dotenv from 'dotenv';

dotenv.config();

export const config = {
  // Server
  nodeEnv: process.env.NODE_ENV || 'development',
  port: parseInt(process.env.PORT || '5005', 10),

  // Redis
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379', 10),
    url: process.env.REDIS_URL || 'redis://localhost:6379',
  },

  // Python RAG Service
  ragService: {
    url: process.env.RAG_SERVICE_URL || 'http://localhost:8005',
    timeout: parseInt(process.env.RAG_SERVICE_TIMEOUT || '600000', 10), // 10 minutes default (CPU systems are slow)
  },

  // CORS
  cors: {
    origin: process.env.CORS_ORIGIN || 'http://localhost:5173',
  },

  // Socket.IO
  socketIO: {
    path: process.env.SOCKET_IO_PATH || '/socket.io',
  },
};
