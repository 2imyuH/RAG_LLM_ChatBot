/**
 * Socket.IO Event Handlers
 * 
 * Handles client connections and room management for job tracking
 */
export function setupSocketHandlers(io) {
  io.on('connection', (socket) => {
    console.log(`[Socket.IO] Client connected: ${socket.id}`);

    // Handle client joining a job room
    socket.on('join_job', (data) => {
      const { jobId } = data;

      if (!jobId) {
        socket.emit('error', { message: 'jobId is required' });
        return;
      }

      // Join room named after jobId
      socket.join(jobId);
      console.log(`[Socket.IO] Client ${socket.id} joined job room: ${jobId}`);

      // Confirm join
      socket.emit('joined_job', {
        jobId,
        message: `Joined job room: ${jobId}`,
      });
    });

    // Handle client leaving a job room
    socket.on('leave_job', (data) => {
      const { jobId } = data;

      if (jobId) {
        socket.leave(jobId);
        console.log(`[Socket.IO] Client ${socket.id} left job room: ${jobId}`);
      }
    });

    // Handle job abortion
    socket.on('abort_job', async (data) => {
      const { jobId } = data;
      if (jobId) {
        console.log(`[Socket.IO] Client ${socket.id} requested abortion for job: ${jobId}`);
        const { abortRAGJob } = await import('../workers/rag.worker.js');
        await abortRAGJob(jobId);
      }
    });

    // Handle disconnection
    socket.on('disconnect', (reason) => {
      console.log(`[Socket.IO] Client ${socket.id} disconnected: ${reason}`);
    });

    // Handle errors
    socket.on('error', (error) => {
      console.error(`[Socket.IO] Socket error for ${socket.id}:`, error);
    });
  });

  console.log('✓ Socket.IO handlers configured');
}
