/**
 * Authentication Middleware
 * Verifies JWT tokens and attaches user info to request
 */
import jwt from 'jsonwebtoken';
import dotenv from 'dotenv';

dotenv.config();

const JWT_SECRET = process.env.JWT_SECRET || 'brotex_secret_key_2026';

/**
 * Middleware to authenticate JWT token
 * Expects: Authorization: Bearer <token>
 * Attaches: req.user = { id, email, name }
 */
export function authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN

    if (!token) {
        return res.status(401).json({
            error: 'Access token required',
            message: 'Please provide a valid authentication token',
        });
    }

    try {
        const user = jwt.verify(token, JWT_SECRET);
        req.user = user; // { id, email, name }
        next();
    } catch (error) {
        if (error.name === 'TokenExpiredError') {
            return res.status(403).json({
                error: 'Token expired',
                message: 'Your session has expired. Please login again.',
            });
        }

        return res.status(403).json({
            error: 'Invalid token',
            message: 'The provided token is invalid or malformed.',
        });
    }
}

/**
 * Generate JWT token for a user
 */
export function generateToken(user) {
    const payload = {
        id: user.id,
        email: user.email,
        name: user.name,
    };

    // Token expires in 7 days
    return jwt.sign(payload, JWT_SECRET, { expiresIn: '7d' });
}

export default { authenticateToken, generateToken };
