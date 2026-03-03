import sqlite3 from 'sqlite3';
import { promisify } from 'util';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DB_PATH = path.join(__dirname, 'chat.db');

const db = new sqlite3.Database(DB_PATH, (err) => {
    if (err) {
        console.error('Error opening database for migration:', err);
        process.exit(1);
    }
});

const dbRun = promisify(db.run.bind(db));

async function migrate() {
    console.log('Starting database migration...');
    try {
        // Try adding reset_token column
        try {
            await dbRun('ALTER TABLE users ADD COLUMN reset_token TEXT');
            console.log('Added reset_token column');
        } catch (e) {
            if (e.message.includes('duplicate column name')) {
                console.log('Column reset_token already exists.');
            } else {
                throw e;
            }
        }

        // Try adding reset_token_expiry column
        try {
            await dbRun('ALTER TABLE users ADD COLUMN reset_token_expiry DATETIME');
            console.log('Added reset_token_expiry column');
        } catch (e) {
            if (e.message.includes('duplicate column name')) {
                console.log('Column reset_token_expiry already exists.');
            } else {
                throw e;
            }
        }

        console.log('Migration completed successfully!');
    } catch (error) {
        console.error('Migration failed:', error);
    } finally {
        db.close();
    }
}

migrate();
