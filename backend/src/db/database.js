/**
 * SQLite Database Initialization and Schema
 * 
 * Tables:
 * - users: User accounts (email/password or Google OAuth)
 * - threads: Chat conversation threads
 * - messages: Individual messages within threads
 */
import sqlite3 from 'sqlite3';
import { promisify } from 'util';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Database file path
const DB_PATH = path.join(__dirname, '../../chat.db');

// Initialize SQLite database
const db = new sqlite3.Database(DB_PATH, (err) => {
    if (err) {
        console.error('Error opening database:', err);
        process.exit(1);
    }
    console.log('📦 Connected to SQLite database:', DB_PATH);
});

// Enable foreign keys
db.run('PRAGMA foreign_keys = ON');

// Promisify database methods for async/await
const dbRun = promisify(db.run.bind(db));
const dbGet = promisify(db.get.bind(db));
const dbAll = promisify(db.all.bind(db));

/**
 * Initialize database schema
 * Creates tables if they don't exist
 */
export async function initializeDatabase() {
    console.log('🔧 Initializing database schema...');

    try {

        // Create users table
        await dbRun(`
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT,
        name TEXT,
        avatar TEXT,
        provider TEXT NOT NULL CHECK(provider IN ('email', 'google')),
        reset_token TEXT,
        reset_token_expiry DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
        console.log('✅ Users table created');

        // Create threads table
        await dbRun(`
      CREATE TABLE IF NOT EXISTS threads (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
      )
    `);
        console.log('✅ Threads table created');

        // Create messages table
        await dbRun(`
      CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
      )
    `);
        console.log('✅ Messages table created');

        // Create indexes for better query performance
        await dbRun('CREATE INDEX IF NOT EXISTS idx_threads_user_id ON threads(user_id)');
        await dbRun('CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id)');

        console.log('✅ Database schema initialized successfully');

    } catch (error) {
        console.error('❌ Error initializing database:', error);
        throw error;
    }
}

/**
 * Database query helpers
 */
export const database = {
    run: dbRun,
    get: dbGet,
    all: dbAll,

    /**
     * Insert a new user
     */
    async createUser(id, email, password, name, avatar, provider) {
        return await dbRun(
            'INSERT INTO users (id, email, password, name, avatar, provider) VALUES (?, ?, ?, ?, ?, ?)',
            [id, email, password, name, avatar, provider]
        );
    },

    /**
     * Find user by email
     */
    async findUserByEmail(email) {
        return await dbGet('SELECT * FROM users WHERE email = ?', [email]);
    },

    /**
     * Find user by ID
     */
    async findUserById(id) {
        return await dbGet('SELECT * FROM users WHERE id = ?', [id]);
    },

    /**
     * Save password reset token
     */
    async saveResetToken(userId, token, expiryStr) {
        return await dbRun(
            'UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?',
            [token, expiryStr, userId]
        );
    },

    /**
     * Find user by valid reset token
     */
    async findUserByValidResetToken(token) {
        return await dbGet(
            'SELECT * FROM users WHERE reset_token = ? AND reset_token_expiry > datetime("now")',
            [token]
        );
    },

    /**
     * Update user password and clear reset token
     */
    async updatePasswordAndClearToken(userId, newPasswordHash) {
        return await dbRun(
            'UPDATE users SET password = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?',
            [newPasswordHash, userId]
        );
    },

    /**
     * Create a new thread
     */
    async createThread(id, userId, title) {
        return await dbRun(
            'INSERT INTO threads (id, user_id, title) VALUES (?, ?, ?)',
            [id, userId, title]
        );
    },

    /**
     * Get all threads for a user
     */
    async getUserThreads(userId) {
        return await dbAll(
            'SELECT * FROM threads WHERE user_id = ? ORDER BY created_at DESC',
            [userId]
        );
    },

    /**
     * Get thread by ID
     */
    async getThreadById(threadId) {
        return await dbGet('SELECT * FROM threads WHERE id = ?', [threadId]);
    },

    /**
     * Delete thread
     */
    async deleteThread(threadId) {
        return await dbRun('DELETE FROM threads WHERE id = ?', [threadId]);
    },

    /**
     * Create a new message
     */
    async createMessage(id, threadId, role, content) {
        return await dbRun(
            'INSERT INTO messages (id, thread_id, role, content) VALUES (?, ?, ?, ?)',
            [id, threadId, role, content]
        );
    },

    /**
     * Get all messages for a thread
     */
    async getThreadMessages(threadId) {
        return await dbAll(
            'SELECT * FROM messages WHERE thread_id = ? ORDER BY created_at ASC, rowid ASC',
            [threadId]
        );
    },

    /**
     * Update thread title
     */
    async updateThread(threadId, title) {
        return await dbRun(
            'UPDATE threads SET title = ? WHERE id = ?',
            [title, threadId]
        );
    },
};

export default database;
