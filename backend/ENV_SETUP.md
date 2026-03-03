# Environment Variables Setup

Create a `.env` file in the `backend/` directory with the following content:

```env
# Node.js Backend Configuration

# Server Configuration
NODE_ENV=development
PORT=5000

# Redis Configuration (for BullMQ)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_URL=redis://localhost:6379

# Python RAG Service Configuration
RAG_SERVICE_URL=http://localhost:8000
RAG_SERVICE_TIMEOUT=300000

# CORS Configuration
CORS_ORIGIN=http://localhost:5173

# Socket.IO Configuration
SOCKET_IO_PATH=/socket.io
```

## Quick Setup

```bash
cd backend
cp ENV_SETUP.md .env
# Then edit .env with your values
```
