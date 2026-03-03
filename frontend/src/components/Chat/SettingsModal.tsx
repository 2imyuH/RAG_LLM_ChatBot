import React from 'react';
import { X, Moon, Sun, Monitor, User, LogOut } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
    const { theme, setTheme } = useTheme();
    const { user, logout } = useAuth();

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 animate-fade-in">
            <div
                className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm"
                onClick={onClose}
            />

            <div className="relative w-full max-w-md glass-card rounded-[2rem] overflow-hidden shadow-2xl animate-slide-up">
                {/* Header */}
                <div className="px-6 py-5 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">Cài đặt</h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-full transition-colors text-slate-500"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>

                <div className="p-6 space-y-8">
                    {/* Profile Section */}
                    <section className="space-y-4">
                        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                            <User className="h-3.5 w-3.5" />
                            Tài khoản
                        </h3>
                        <div className="flex items-center gap-4 p-4 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700">
                            <div className="h-12 w-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-xl font-bold text-white shadow-lg">
                                {user?.name?.[0] || 'B'}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="font-bold text-slate-900 dark:text-white truncate">{user?.name || 'Brotex User'}</p>
                                <p className="text-sm text-slate-500 dark:text-slate-400 truncate">{user?.email || 'user@brotex.com'}</p>
                            </div>
                        </div>
                    </section>

                    {/* Theme Section */}
                    <section className="space-y-4">
                        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                            <Sun className="h-3.5 w-3.5" />
                            Giao diện
                        </h3>
                        <div className="grid grid-cols-3 gap-2">
                            {[
                                { id: 'light', icon: Sun, label: 'Sáng' },
                                { id: 'dark', icon: Moon, label: 'Tối' },
                                { id: 'system', icon: Monitor, label: 'Hệ thống' }
                            ].map((t) => (
                                <button
                                    key={t.id}
                                    onClick={() => setTheme(t.id as any)}
                                    className={`flex flex-col items-center gap-2 p-3 rounded-2xl border transition-all ${theme === t.id
                                            ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-500 text-blue-600 dark:text-blue-400'
                                            : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-500 hover:border-slate-300 dark:hover:border-slate-600'
                                        }`}
                                >
                                    <t.icon className="h-5 w-5" />
                                    <span className="text-xs font-bold">{t.label}</span>
                                </button>
                            ))}
                        </div>
                    </section>

                    {/* Actions */}
                    <section className="pt-2">
                        <button
                            onClick={() => {
                                logout();
                                onClose();
                            }}
                            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-2xl bg-rose-50 dark:bg-rose-900/10 text-rose-600 dark:text-rose-400 font-bold hover:bg-rose-100 dark:hover:bg-rose-900/20 transition-all border border-rose-200/50 dark:border-rose-900/30"
                        >
                            <LogOut className="h-4 w-4" />
                            Đăng xuất
                        </button>
                    </section>
                </div>
            </div>
        </div>
    );
};
