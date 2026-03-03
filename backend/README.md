# RAG Backend Service

Node.js/Express backend for managing RAG queries with job queue and real-time updates.

## Architecture

- **Express**: HTTP API server
- **BullMQ**: Job queue system (requires Redis)
- **Socket.IO**: Real-time communication
- **Axios**: HTTP client for Python RAG service

## Project Structure

```
backend/
├── src/
│   ├── server.js           # Main entry point
│   ├── config/
│   │   └── config.js       # Configuration from .env
│   ├── routes/
│   │   └── chat.routes.js   # API route handlers
│   ├── queues/
│   │   └── rag.queue.js     # BullMQ queue setup
│   ├── workers/
│   │   └── rag.worker.js    # Queue worker (processes jobs)
│   └── sockets/
│       └── socket.handler.js # Socket.IO handlers
├── package.json
├── .env.example
└── README.md
```

## Workflow

1. **Client** sends `POST /api/chat` with query
2. **Server** creates job in BullMQ queue and returns `jobId` immediately
3. **Worker** picks up job and calls Python RAG service
4. **Worker** emits Socket.IO event when complete
5. **Client** receives real-time update via Socket.IO

## Setup

1. Install dependencies:
```bash
npm install
```

2. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

3. Ensure Redis is running:
```bash
# Redis must be running on localhost:6379
# Or configure REDIS_URL in .env
```

4. Start the server:
```bash
npm start
# or for development with auto-reload:
npm run dev
```

## Environment Variables

See `.env.example` for all configuration options.

Key variables:
- `PORT`: Backend server port (default: 5000)
- `REDIS_URL`: Redis connection string
- `RAG_SERVICE_URL`: Python RAG service URL (default: http://localhost:8000)
- `RAG_SERVICE_TIMEOUT`: Timeout for Python requests in ms (default: 300000 = 5 minutes)
- `CORS_ORIGIN`: Frontend origin for CORS (default: http://localhost:5173)

## API Endpoints

- `POST /api/chat` - Submit a query, returns `{ jobId: "..." }`
- `GET /api/health` - Health check
- `GET /api/job/:jobId` - Get job status (optional, Socket.IO is primary)

## Socket.IO Events

### Client → Server
- `join_job` - Join room for jobId
  ```js
  socket.emit('join_job', { jobId: '...' });
  ```
- `leave_job` - Leave job room
  ```js
  socket.emit('leave_job', { jobId: '...' });
  ```

### Server → Client
- `joined_job` - Confirmation of joining job room
- `chat_complete` - Job completed with result
  ```js
  {
    jobId: "...",
    answer: "...",
    latency_ms: 145000,
    duration_seconds: "145.23",
    timestamp: "2024-01-15T10:02:25.000Z"
  }
  ```
- `chat_error` - Job failed with error
  ```js
  {
    jobId: "...",
    error: "Error message",
    errorType: "timeout|connection_refused|service_error|network_error",
    timestamp: "2024-01-15T10:02:25.000Z",
    duration_seconds: "145.23"
  }
  ```

## Usage Example

### 1. Submit Query (HTTP)
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG?"}'
```

Response:
```json
{
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Query submitted successfully. Use Socket.IO to receive updates.",
  "socketEvent": "join_job",
  "timestamp": "2024-01-15T10:00:00.000Z"
}
```

### 2. Receive Updates (Socket.IO)
```javascript
import { io } from 'socket.io-client';

const socket = io('http://localhost:5000', {
  path: '/socket.io'
});

socket.on('connect', () => {
  socket.emit('join_job', { jobId: '550e8400-e29b-41d4-a716-446655440000' });
});

socket.on('chat_complete', (data) => {
  console.log('Answer:', data.answer);
});

socket.on('chat_error', (data) => {
  console.error('Error:', data.error);
});
```

## Testing

Run the test script:
```bash
# Test health endpoint
npm test

# Test chat endpoint with query
node test_api.js "Your query here"
```

## Implementation Details

### Critical Constraints Applied

1. **Worker Concurrency = 1**
   - Jobs are processed sequentially (one at a time)
   - Prevents overloading the Python RAG service
   - Configured in `src/workers/rag.worker.js`

2. **Robust Error Handling**
   - All errors are emitted via Socket.IO `chat_error` event
   - Frontend always receives error notifications
   - Detailed error types: timeout, connection_refused, service_error, network_error

3. **Detailed Latency Logging**
   - Start time, end time, and duration logged for each job
   - Format: `[Job 123] Sent to Python at 10:00:00... Received response at 10:02:25 (Duration: 145s)`

4. **Redis Connection**
   - Uses `REDIS_HOST` and `REDIS_PORT` environment variables
   - Supports both local Redis and Docker Redis
   - Falls back to `REDIS_URL` if provided

## Notes

- Jobs are processed asynchronously via BullMQ
- Long-running queries (145s+) are handled gracefully with 5-minute timeout
- Real-time updates via Socket.IO rooms (one per jobId)
- Python service timeout set to 300 seconds (5 minutes)
- Worker processes jobs sequentially to prevent system overload
