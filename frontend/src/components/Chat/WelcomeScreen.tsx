import React from 'react';
import { Sparkles, MessageSquare, BookOpen, Lightbulb, ArrowRight } from 'lucide-react';

interface WelcomeScreenProps {
    onSelectPrompt: (prompt: string) => void;
}

const suggestedPrompts = [
    {
        title: 'Quy trình R&D',
        description: 'Quy trình phát triển sản phẩm dệt may tại Brotex như thế nào?',
        icon: Sparkles,
        color: 'text-blue-500',
        bg: 'bg-blue-50 dark:bg-blue-900/20',
    },
    {
        title: 'Thông số Kỹ thuật',
        description: 'Tính toán tỷ lệ sợi và độ co rút cho mã hàng Cotton 100%.',
        icon: BookOpen,
        color: 'text-emerald-500',
        bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    },
    {
        title: 'Giải pháp Sản xuất',
        description: 'Xử lý lỗi nhuộm không đều màu trên vải Polyester.',
        icon: Lightbulb,
        color: 'text-amber-500',
        bg: 'bg-amber-50 dark:bg-amber-900/20',
    },
    {
        title: 'Lịch sử Hội thoại',
        description: 'Xem lại các ghi chú về dự án dệt nhuộm tuần trước.',
        icon: MessageSquare,
        color: 'text-indigo-500',
        bg: 'bg-indigo-50 dark:bg-indigo-900/20',
    }
];

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onSelectPrompt }) => {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] py-12 px-4 text-center animate-fade-in">
            {/* Hero Header */}
            <div className="mb-12 relative">
                <div className="absolute -inset-4 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full blur-3xl opacity-10 dark:opacity-20 animate-pulse-subtle"></div>
                <div className="relative h-20 w-20 rounded-3xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-2xl mb-6 mx-auto transform hover:rotate-6 transition-transform duration-500">
                    <Sparkles className="h-10 w-10 text-white" />
                </div>
                <h1 className="text-4xl md:text-5xl font-black text-slate-900 dark:text-white mb-4 tracking-tight">
                    Brotex <span className="text-blue-600 dark:text-blue-500 italic">Intelligent</span> Assistant
                </h1>
                <p className="text-lg text-slate-500 dark:text-slate-400 max-w-xl mx-auto font-medium">
                    Trợ lý AI chuyên biệt cho bộ phận Nghiên cứu & Phát triển tại Brotex.
                    Sẵn sàng hỗ trợ bạn về quy trình, kỹ thuật và dữ liệu.
                </p>
            </div>

            {/* Suggested Prompts Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-3xl">
                {suggestedPrompts.map((prompt, idx) => (
                    <button
                        key={idx}
                        onClick={() => onSelectPrompt(prompt.description)}
                        className="group flex flex-col items-start p-5 rounded-[2rem] border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 hover:border-blue-500 dark:hover:border-blue-500 hover:shadow-xl hover:shadow-blue-500/5 transition-all duration-300 text-left relative overflow-hidden"
                    >
                        <div className={`p-3 rounded-2xl ${prompt.bg} ${prompt.color} mb-4 group-hover:scale-110 transition-transform`}>
                            <prompt.icon className="h-5 w-5" />
                        </div>
                        <h3 className="font-bold text-slate-900 dark:text-white mb-1">{prompt.title}</h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400 line-clamp-2">{prompt.description}</p>
                        <div className="absolute right-6 bottom-6 opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 transition-all">
                            <ArrowRight className="h-4 w-4 text-blue-600 dark:text-blue-500" />
                        </div>
                    </button>
                ))}
            </div>

            {/* Trust Footer */}
            <p className="mt-12 text-xs font-bold text-slate-400 dark:text-slate-600 uppercase tracking-[0.2em]">
                Secured RAG Pipeline • Internal Use Only
            </p>
        </div>
    );
};
