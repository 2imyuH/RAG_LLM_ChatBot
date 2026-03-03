/**
 * Authentication Routes
 * POST /api/auth/google - Google OAuth login
 * POST /api/auth/register - Email/password registration
 * POST /api/auth/login - Email/password login
 */
import express from 'express';
import { googleLogin, register, login, getMe, forgotPassword, verifyOTP, resetPassword } from '../controllers/authController.js';
import { authenticateToken } from '../middleware/authMiddleware.js';

export const authRoutes = express.Router();

authRoutes.post('/auth/google', googleLogin);
authRoutes.post('/auth/register', register);
authRoutes.post('/auth/login', login);
authRoutes.post('/auth/forgot-password', forgotPassword);
authRoutes.post('/auth/verify-otp', verifyOTP);
authRoutes.post('/auth/reset-password', resetPassword);
authRoutes.get('/auth/me', authenticateToken, getMe);

export default authRoutes;
