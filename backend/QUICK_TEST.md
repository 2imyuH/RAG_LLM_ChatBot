# Quick Test Guide

## Prerequisites

1. **Backend Server Running**
   ```bash
   cd backend
   npm start
   ```

2. **Redis Running**
   ```bash
   # Docker Redis (if using Docker)
   docker run -d --name redis-temp -p 6379:6379 redis:alpine
   
   # Or local Redis installation
   ```

3. **Python RAG Service Running**
   ```bash
   # Should be running on port 8005 (or configured port)
   ```

## Running Tests

### 1. Health Check
```bash
cd backend
node test_api.js
```

Expected output:
```
✓ Health check passed
```

### 2. Full Chat Flow Test
```bash
cd backend
node test_api.js "Your query here"
```

Example:
```bash
node test_api.js "Đèn D65 là gì?"
```

Expected flow:
1. ✅ Health check passes
2. ✅ Chat request submitted (returns jobId immediately)
3. ✅ Socket.IO connects
4. ✅ Joins job room
5. ✅ Waits for completion (~2-3 minutes)
6. ✅ Receives answer via Socket.IO

## Manual Testing with curl

### Health Check
```bash
curl http://localhost:5005/api/health
```

### Submit Query
```bash
curl -X POST http://localhost:5005/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Your query here"}'
```

Response:
```json
{
  "jobId": "uuid-here",
  "status": "queued",
  "message": "Query submitted successfully. Use Socket.IO to receive updates.",
  "socketEvent": "join_job",
  "timestamp": "2026-01-15T06:15:42.992Z"
}
```

### Check Job Status (Optional)
```bash
curl http://localhost:5005/api/job/{jobId}
```

## Socket.IO Testing

Use a Socket.IO client or the test script:

```javascript
import { io } from 'socket.io-client';

const socket = io('http://localhost:5005', {
  path: '/socket.io'
});

socket.on('connect', () => {
  socket.emit('join_job', { jobId: 'your-job-id' });
});

socket.on('chat_complete', (data) => {
  console.log('Answer:', data.answer);
});

socket.on('chat_error', (data) => {
  console.error('Error:', data.error);
});
```

## Troubleshooting

### Port Already in Use
- Change `PORT` in `.env` file
- Or kill the process using port 5005

### Redis Connection Failed
- Ensure Redis is running: `redis-cli ping`
- Check `REDIS_HOST` and `REDIS_PORT` in `.env`

### Python Service Not Responding
- Check `RAG_SERVICE_URL` in `.env`
- Verify Python service is running
- Check Python service logs

### Socket.IO Not Connecting
- Verify CORS settings
- Check Socket.IO path configuration
- Ensure firewall allows WebSocket connections
