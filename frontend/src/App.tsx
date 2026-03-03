import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ChatLayout } from './components/Chat/ChatLayout';
import { useChat } from './hooks/useChat';
import LoginPage from './pages/LoginPage';

const GOOGLE_CLIENT_ID = '694684260774-1b3r9td5sfg4u7oufnggg727n5glfl4m.apps.googleusercontent.com';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

function ChatApp() {
  const {
    messages,
    statusStep,
    elapsedSeconds,
    sendMessage,
    error,
    isLoading,
    clearError,
    threads,
    currentThreadId,
    selectThread,
    deleteThread,
    renameThread,
    stopGeneration
  } = useChat();

  return (
    <ChatLayout
      messages={messages}
      statusStep={statusStep}
      elapsedSeconds={elapsedSeconds}
      isLoading={isLoading}
      error={error}
      threads={threads}
      currentThreadId={currentThreadId}
      onSend={sendMessage}
      onStop={stopGeneration}
      onSelectThread={selectThread}
      onDeleteThread={deleteThread}
      onRenameThread={renameThread}
      onDismissError={clearError}
      profile="CONSUMER"
    />
  );
}

function AppContent() {
  const { loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="text-gray-500 font-medium animate-pulse">Initializing Brotex AI...</p>
        </div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ChatApp />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

import { ThemeProvider } from './context/ThemeContext';

function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AuthProvider>
        <ThemeProvider>
          <Router>
            <AppContent />
          </Router>
        </ThemeProvider>
      </AuthProvider>
    </GoogleOAuthProvider>
  );
}

export default App;
