import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Shield, Mail, Lock, User, Loader2 } from 'lucide-react';
import api from '../api/api';

const LoginPage: React.FC = () => {
    const [isLogin, setIsLogin] = useState(true);
    const [isForgotPassword, setIsForgotPassword] = useState(false);
    const [isVerifyOTP, setIsVerifyOTP] = useState(false);
    const [isResetPassword, setIsResetPassword] = useState(false);

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [name, setName] = useState('');
    const [otpCode, setOtpCode] = useState('');
    const [resetSessionToken, setResetSessionToken] = useState('');

    const [error, setError] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    const [loading, setLoading] = useState(false);

    const { login, register, loginGoogle } = useAuth();
    const navigate = useNavigate();


    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccessMsg('');
        setLoading(true);
        try {
            if (isResetPassword) {
                // Step 3: Handle Final Reset Password
                await api.post('/auth/reset-password', {
                    token: resetSessionToken,
                    newPassword: password
                });

                setSuccessMsg('Password reset successfully! Please login.');
                setIsResetPassword(false);
                setIsLogin(true);
                setPassword('');
            } else if (isVerifyOTP) {
                // Step 2: Handle Verify OTP
                const response = await api.post('/auth/verify-otp', { email, otp: otpCode });
                setResetSessionToken(response.data.resetSessionToken);

                setSuccessMsg('OTP verified! Please enter your new password.');
                setIsVerifyOTP(false);
                setIsResetPassword(true);
            } else if (isForgotPassword) {
                // Step 1: Handle Forgot Password (Send OTP)
                await api.post('/auth/forgot-password', { email });

                setSuccessMsg('A 6-digit verification code has been sent to your email.');
                setIsForgotPassword(false);
                setIsVerifyOTP(true); // Move to OTP input step
            } else if (isLogin) {
                await login(email, password);
                navigate('/');
            } else {
                await register(email, password, name);
                navigate('/');
            }
        } catch (err: any) {
            setError(err.response?.data?.error || err.message || 'Authentication failed');
        } finally {
            setLoading(false);
        }
    };

    const handleGoogleSuccess = async (credentialResponse: any) => {
        setLoading(true);
        try {
            await loginGoogle(credentialResponse.credential);
            navigate('/');
        } catch (err: any) {
            console.error("Google Auth Frontend Error:", err);
            setError(err.message || err.response?.data?.message || err.response?.data?.error || 'Google login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
            <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-2xl shadow-xl border border-gray-100">
                <div className="text-center">
                    <div className="mx-auto h-12 w-12 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg transform rotate-6">
                        <Shield className="h-8 w-8 text-white" />
                    </div>
                    <h2 className="mt-6 text-3xl font-extrabold text-gray-900 tracking-tight">
                        Brotex R&D
                    </h2>
                    <p className="mt-2 text-sm text-gray-500">
                        Intelligent Assistant Platform
                    </p>
                </div>

                <div className="flex p-1 bg-gray-100 rounded-lg">
                    <button
                        onClick={() => { setIsLogin(true); setIsForgotPassword(false); setIsVerifyOTP(false); setIsResetPassword(false); setError(''); setSuccessMsg(''); }}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${isLogin && !isForgotPassword && !isVerifyOTP && !isResetPassword ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                            }`}
                    >
                        Login
                    </button>
                    <button
                        onClick={() => { setIsLogin(false); setIsForgotPassword(false); setIsVerifyOTP(false); setIsResetPassword(false); setError(''); setSuccessMsg(''); }}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${!isLogin && !isForgotPassword && !isVerifyOTP && !isResetPassword ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                            }`}
                    >
                        Register
                    </button>
                </div>

                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    {error && (
                        <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm border border-red-100 animate-pulse">
                            {error}
                        </div>
                    )}
                    {successMsg && (
                        <div className="bg-emerald-50 text-emerald-600 p-3 rounded-lg text-sm border border-emerald-100">
                            {successMsg}
                        </div>
                    )}
                    <div className="space-y-4">
                        {isResetPassword ? (
                            <>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
                                    <input
                                        type="password"
                                        required
                                        placeholder="Enter New Password (min 6 chars)"
                                        className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                    />
                                </div>
                            </>
                        ) : isVerifyOTP ? (
                            <>
                                <div className="text-center mb-4">
                                    <p className="text-sm text-gray-600 font-medium tracking-wide">Enter the 6-digit code sent to <span className="font-bold text-gray-800">{email}</span></p>
                                </div>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-3 h-5 w-5 text-indigo-400" />
                                    <input
                                        type="text"
                                        required
                                        maxLength={6}
                                        placeholder="123456"
                                        className="w-full pl-10 pr-4 py-3 bg-indigo-50 border border-indigo-200 rounded-lg focus:ring-2 focus:ring-indigo-500 font-bold tracking-[0.5em] text-center text-indigo-900 transition-all outline-none"
                                        value={otpCode}
                                        onChange={(e) => setOtpCode(e.target.value.replace(/[^0-9]/g, ''))}
                                    />
                                </div>
                            </>
                        ) : isForgotPassword ? (
                            <div className="relative">
                                <Mail className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
                                <input
                                    type="email"
                                    required
                                    placeholder="Enter your registered email"
                                    className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                />
                            </div>
                        ) : (
                            <>
                                {!isLogin && (
                                    <div className="relative">
                                        <User className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
                                        <input
                                            type="text"
                                            required
                                            placeholder="Full Name"
                                            className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                            value={name}
                                            onChange={(e) => setName(e.target.value)}
                                        />
                                    </div>
                                )}
                                <div className="relative">
                                    <Mail className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
                                    <input
                                        type="email"
                                        required
                                        placeholder="Email Address"
                                        className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                    />
                                </div>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
                                    <input
                                        type="password"
                                        required
                                        placeholder="Password"
                                        className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                    />
                                </div>
                                {isLogin && (
                                    <div className="flex justify-end">
                                        <button
                                            type="button"
                                            onClick={() => { setIsForgotPassword(true); setError(''); setSuccessMsg(''); }}
                                            className="text-sm text-blue-600 hover:text-blue-500 font-medium"
                                        >
                                            Forgot your password?
                                        </button>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    <div className="space-y-3">
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors disabled:opacity-50"
                        >
                            {loading ? (
                                <Loader2 className="h-5 w-5 animate-spin" />
                            ) : (
                                isResetPassword ? 'Set New Password' : isVerifyOTP ? 'Verify OTP' : isForgotPassword ? 'Send Reset Link' : isLogin ? 'Sign In' : 'Create Account'
                            )}
                        </button>
                        {(isForgotPassword || isVerifyOTP || isResetPassword) && (
                            <div className="text-center">
                                <button
                                    type="button"
                                    onClick={() => { setIsForgotPassword(false); setIsVerifyOTP(false); setIsResetPassword(false); setError(''); setSuccessMsg(''); }}
                                    className="text-sm text-gray-500 hover:text-gray-700 font-medium"
                                >
                                    Back to login
                                </button>
                            </div>
                        )}
                    </div>
                </form>

                <div className="mt-6">
                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-gray-200" />
                        </div>
                        <div className="relative flex justify-center text-sm">
                            <span className="px-2 bg-white text-gray-500">Or continue with</span>
                        </div>
                    </div>

                    <div className="mt-6 flex justify-center">
                        <GoogleLogin
                            onSuccess={handleGoogleSuccess}
                            onError={() => setError('Google login failed')}
                            useOneTap
                            shape="pill"
                            theme="outline"
                            size="large"
                            text="continue_with"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;
