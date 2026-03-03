import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/api';

interface User {
    id: string;
    email: string;
    name: string;
    avatar?: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    loading: boolean;
    login: (email: string, pass: string) => Promise<void>;
    loginGoogle: (credential: string) => Promise<void>;
    register: (email: string, pass: string, name: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const initializeAuth = async () => {
            const savedToken = localStorage.getItem('token');
            if (!savedToken) {
                setLoading(false);
                return;
            }

            try {
                setLoading(true);
                // Verify token with backend
                const response = await api.get('/auth/me');
                const { user: userData } = response.data;

                setToken(savedToken);
                setUser(userData);
            } catch (error) {
                console.error('[Auth] Initialization failed:', error);
                logout();
            } finally {
                setLoading(false);
            }
        };

        initializeAuth();
    }, []);

    const login = async (email: string, pass: string) => {
        const response = await api.post('/auth/login', { email, password: pass });
        const { token, user } = response.data;
        handleAuthResponse(token, user);
    };

    const loginGoogle = async (credential: string) => {
        const response = await api.post('/auth/google', { token: credential });
        const { token, user } = response.data;
        handleAuthResponse(token, user);
    };

    const register = async (email: string, pass: string, name: string) => {
        const response = await api.post('/auth/register', { email, password: pass, name });
        const { token, user } = response.data;
        handleAuthResponse(token, user);
    };

    const handleAuthResponse = (newToken: string, newUser: User) => {
        setToken(newToken);
        setUser(newUser);
        localStorage.setItem('token', newToken);
        localStorage.setItem('user', JSON.stringify(newUser));
    };

    const logout = () => {
        setToken(null);
        setUser(null);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    };

    return (
        <AuthContext.Provider value={{ user, token, loading, login, loginGoogle, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
