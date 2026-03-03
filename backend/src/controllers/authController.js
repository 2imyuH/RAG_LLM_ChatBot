/**
 * Authentication Controller
 * Handles Google OAuth, Email/Password Registration and Login
 */
import { v4 as uuidv4 } from 'uuid';
import bcrypt from 'bcryptjs';
import crypto from 'crypto';
import { OAuth2Client } from 'google-auth-library';
import dotenv from 'dotenv';
import { database } from '../db/database.js';
import { generateToken } from '../middleware/authMiddleware.js';
import { sendPasswordResetOTP } from '../services/emailService.js';

dotenv.config();

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID || '694684260774-1b3r9td5sfg4u7oufnggg727n5glfl4m.apps.googleusercontent.com';
const googleClient = new OAuth2Client(GOOGLE_CLIENT_ID);

/**
 * POST /api/auth/google
 * Google OAuth Login/Register
 */
export async function googleLogin(req, res) {
    try {
        const { token } = req.body;

        if (!token) {
            return res.status(400).json({ error: 'Google token is required' });
        }

        // Verify Google token
        const ticket = await googleClient.verifyIdToken({
            idToken: token,
            audience: GOOGLE_CLIENT_ID,
        });

        const payload = ticket.getPayload();
        const { email, name, picture } = payload;

        if (!email) {
            return res.status(400).json({ error: 'Email not provided by Google' });
        }

        // Check if user exists
        let user = await database.findUserByEmail(email);

        if (!user) {
            // Create new user
            const userId = uuidv4();
            await database.createUser(
                userId,
                email,
                null, // No password for Google OAuth
                name || email.split('@')[0],
                picture || null,
                'google'
            );

            user = await database.findUserById(userId);
            console.log(`[Auth] New Google user created: ${email}`);
        } else {
            console.log(`[Auth] Existing Google user logged in: ${email}`);
        }

        // Generate JWT
        const jwtToken = generateToken(user);

        res.json({
            token: jwtToken,
            user: {
                id: user.id,
                email: user.email,
                name: user.name,
                avatar: user.avatar,
            },
        });

    } catch (error) {
        console.error('[Auth] Google login error details:', error);
        res.status(500).json({
            error: 'Google authentication failed',
            message: error.message,
            stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
        });
    }
}

/**
 * POST /api/auth/register
 * Email/Password Registration
 */
export async function register(req, res) {
    try {
        const { email, password, name } = req.body;

        // Validation
        if (!email || !password) {
            return res.status(400).json({ error: 'Email and password are required' });
        }

        if (password.length < 6) {
            return res.status(400).json({ error: 'Password must be at least 6 characters' });
        }

        // Email format validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            return res.status(400).json({ error: 'Invalid email format' });
        }

        // Check if user already exists
        const existingUser = await database.findUserByEmail(email);
        if (existingUser) {
            return res.status(409).json({ error: 'Email already registered' });
        }

        // Hash password
        const hashedPassword = await bcrypt.hash(password, 10);

        // Create user
        const userId = uuidv4();
        await database.createUser(
            userId,
            email,
            hashedPassword,
            name || email.split('@')[0],
            null, // No avatar for email users
            'email'
        );

        const user = await database.findUserById(userId);
        console.log(`[Auth] New email user registered: ${email}`);

        // Generate JWT
        const token = generateToken(user);

        res.status(201).json({
            token,
            user: {
                id: user.id,
                email: user.email,
                name: user.name,
                avatar: user.avatar,
            },
        });

    } catch (error) {
        console.error('[Auth] Registration error:', error);
        res.status(500).json({
            error: 'Registration failed',
            message: error.message,
        });
    }
}

/**
 * POST /api/auth/login
 * Email/Password Login
 */
export async function login(req, res) {
    try {
        const { email, password } = req.body;

        // Validation
        if (!email || !password) {
            return res.status(400).json({ error: 'Email and password are required' });
        }

        // Find user
        const user = await database.findUserByEmail(email);
        if (!user) {
            return res.status(401).json({ error: 'Invalid email or password' });
        }

        // Check if user registered with Google
        if (user.provider === 'google') {
            return res.status(400).json({
                error: 'This account uses Google Sign-In',
                message: 'Please use the "Sign in with Google" button',
            });
        }

        // Verify password
        const isValidPassword = await bcrypt.compare(password, user.password);
        if (!isValidPassword) {
            return res.status(401).json({ error: 'Invalid email or password' });
        }

        console.log(`[Auth] Email user logged in: ${email}`);

        // Generate JWT
        const token = generateToken(user);

        res.json({
            token,
            user: {
                id: user.id,
                email: user.email,
                name: user.name,
                avatar: user.avatar,
            },
        });

    } catch (error) {
        console.error('[Auth] Login error:', error);
        res.status(500).json({
            error: 'Login failed',
            message: error.message,
        });
    }
}

/**
 * GET /api/auth/me
 * Get current user profile
 */
export async function getMe(req, res) {
    try {
        // req.user is attached by authenticateToken middleware
        const user = await database.findUserById(req.user.id);
        if (!user) {
            return res.status(404).json({ error: 'User not found' });
        }

        res.json({
            user: {
                id: user.id,
                email: user.email,
                name: user.name,
                avatar: user.avatar,
            },
        });
    } catch (error) {
        console.error('[Auth] getMe error:', error);
        res.status(500).json({ error: 'Failed to fetch user profile' });
    }
}

/**
 * POST /api/auth/forgot-password
 * Generate a reset token for the given email
 */
export async function forgotPassword(req, res) {
    try {
        const { email } = req.body;

        if (!email) {
            return res.status(400).json({ error: 'Email is required' });
        }

        const user = await database.findUserByEmail(email);

        // Always return success even if user doesn't exist (security best practice)
        if (!user) {
            console.log(`[Auth] Forgot password requested for non-existent email: ${email}`);
            return res.json({ message: 'If an account exists, a reset link will be sent.' });
        }

        if (user.provider === 'google') {
            return res.status(400).json({
                error: 'This account uses Google Sign-In',
                message: 'Password reset is not available for Google accounts.'
            });
        }

        // Generate a 6-digit numeric OTP
        const otpCode = Math.floor(100000 + Math.random() * 900000).toString();

        // Expiry time (10 minutes from now)
        const expiryDate = new Date();
        expiryDate.setMinutes(expiryDate.getMinutes() + 10);
        const expiryStr = expiryDate.toISOString().replace('T', ' ').substring(0, 19);

        await database.saveResetToken(user.id, otpCode, expiryStr);

        // Send email with OTP
        await sendPasswordResetOTP(email, otpCode);

        res.json({
            message: 'If the email is registered, a 6-digit code has been sent.'
        });

    } catch (error) {
        console.error('[Auth] Forgot password error:', error);
        res.status(500).json({ error: 'Failed to process forgot password request', message: error.message });
    }
}

/**
 * POST /api/auth/verify-otp
 * Verify the 6-digit OTP and return a secure session token to reset the password
 */
export async function verifyOTP(req, res) {
    try {
        const { email, otp } = req.body;

        if (!email || !otp) {
            return res.status(400).json({ error: 'Email and OTP code are required' });
        }

        const user = await database.findUserByEmail(email);

        if (!user || user.reset_token !== otp) {
            return res.status(400).json({ error: 'Invalid or incorrect OTP code' });
        }

        const now = new Date();
        const expiry = new Date(user.reset_token_expiry + 'Z'); // Handle UTC properly

        if (now > expiry) {
            return res.status(400).json({ error: 'OTP code has expired. Please request a new one.' });
        }

        // Generate a random secure session token to authorize the actual DB reset
        const resetSessionToken = crypto.randomBytes(32).toString('hex');

        // Update DB: the token is now the secure hex ticket instead of the OTP, lasting another 15 minutes
        const sessionExpiryDate = new Date();
        sessionExpiryDate.setMinutes(sessionExpiryDate.getMinutes() + 15);
        const sessionExpiryStr = sessionExpiryDate.toISOString().replace('T', ' ').substring(0, 19);

        await database.saveResetToken(user.id, resetSessionToken, sessionExpiryStr);

        res.json({
            message: 'OTP verified successfully',
            resetSessionToken: resetSessionToken
        });

    } catch (error) {
        console.error('[Auth] Verify OTP error:', error);
        res.status(500).json({ error: 'Failed to verify OTP', message: error.message });
    }
}

/**
 * POST /api/auth/reset-password
 * Reset password using a valid token
 */
export async function resetPassword(req, res) {
    try {
        const { token, newPassword } = req.body;

        if (!token || !newPassword) {
            return res.status(400).json({ error: 'Token and new password are required' });
        }

        if (newPassword.length < 6) {
            return res.status(400).json({ error: 'Password must be at least 6 characters' });
        }

        const user = await database.findUserByValidResetToken(token);

        if (!user) {
            return res.status(400).json({ error: 'Invalid or expired reset token' });
        }

        // Hash new password
        const hashedPassword = await bcrypt.hash(newPassword, 10);

        // Update password and clear token
        await database.updatePasswordAndClearToken(user.id, hashedPassword);

        console.log(`[Auth] Password reset successfully for user: ${user.email}`);

        res.json({ message: 'Password has been successfully reset' });

    } catch (error) {
        console.error('[Auth] Reset password error:', error);
        res.status(500).json({ error: 'Failed to reset password', message: error.message });
    }
}

export default { googleLogin, register, login, getMe, forgotPassword, verifyOTP, resetPassword };
