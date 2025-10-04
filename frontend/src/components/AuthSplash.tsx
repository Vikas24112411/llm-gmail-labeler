import React, { useState, useEffect } from 'react';
import { Mail, Key, CheckCircle, AlertCircle, Loader } from 'lucide-react';

interface AuthSplashProps {
  onAuthComplete: () => void;
}

const AuthSplash: React.FC<AuthSplashProps> = ({ onAuthComplete }) => {
  const [authStatus, setAuthStatus] = useState<'checking' | 'needed' | 'authenticating' | 'success' | 'error'>('checking');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await fetch('http://localhost:8502/api/auth/status');
      const data = await response.json();
      
      if (data.authenticated) {
        setAuthStatus('success');
        setTimeout(() => onAuthComplete(), 1000);
      } else {
        setAuthStatus('needed');
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
      setAuthStatus('error');
      setErrorMessage('Cannot connect to backend. Make sure the server is running on port 8502.');
    }
  };

  const handleAuthenticate = async () => {
    setAuthStatus('authenticating');
    setErrorMessage('');

    try {
      const response = await fetch('http://localhost:8502/api/auth/gmail', {
        method: 'POST',
      });

      if (response.ok) {
        setAuthStatus('success');
        setTimeout(() => onAuthComplete(), 1000);
      } else {
        const error = await response.json();
        setAuthStatus('error');
        setErrorMessage(error.detail || 'Authentication failed. Please try again.');
      }
    } catch (error) {
      console.error('Authentication error:', error);
      setAuthStatus('error');
      setErrorMessage('Failed to authenticate. Please check that:\n1. Backend server is running\n2. client_secret.json is in backend/credentials/\n3. You complete the OAuth flow in the popup window');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full">
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full mb-4">
            <Mail className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            LLM Gmail Labeler
          </h1>
          <p className="text-gray-600">
            AI-powered email organization
          </p>
        </div>

        {/* Status Content */}
        <div className="space-y-6">
          {/* Checking Status */}
          {authStatus === 'checking' && (
            <div className="text-center py-8">
              <Loader className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
              <p className="text-gray-600">Checking authentication status...</p>
            </div>
          )}

          {/* Authentication Needed */}
          {authStatus === 'needed' && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <Key className="w-6 h-6 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-blue-900 mb-1">
                      Authentication Required
                    </h3>
                    <p className="text-sm text-blue-700">
                      Connect your Gmail account to start organizing emails with AI
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-3 text-sm text-gray-600">
                <p className="font-medium text-gray-700">What happens next:</p>
                <ul className="space-y-2">
                  <li className="flex items-start space-x-2">
                    <span className="text-blue-500 font-bold flex-shrink-0">1.</span>
                    <span>A Google OAuth window will open</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <span className="text-blue-500 font-bold flex-shrink-0">2.</span>
                    <span>Select your Gmail account</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <span className="text-blue-500 font-bold flex-shrink-0">3.</span>
                    <span>Grant permissions to read and label emails</span>
                  </li>
                  <li className="flex items-start space-x-2">
                    <span className="text-blue-500 font-bold flex-shrink-0">4.</span>
                    <span>Start using the app!</span>
                  </li>
                </ul>
              </div>

              <button
                onClick={handleAuthenticate}
                className="w-full bg-gradient-to-r from-blue-500 to-indigo-600 text-white py-3 px-6 rounded-lg font-semibold hover:from-blue-600 hover:to-indigo-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-105"
              >
                Authenticate with Google
              </button>

              <p className="text-xs text-gray-500 text-center">
                🔒 Your data stays on your machine. We only request necessary Gmail permissions.
              </p>
            </div>
          )}

          {/* Authenticating */}
          {authStatus === 'authenticating' && (
            <div className="text-center py-8">
              <Loader className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Authenticating...
              </h3>
              <p className="text-gray-600 mb-4">
                Please complete the OAuth flow in the popup window
              </p>
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p className="text-sm text-yellow-800">
                  <strong>Note:</strong> If no popup appeared, check if your browser blocked it.
                  The authentication window should open automatically.
                </p>
              </div>
            </div>
          )}

          {/* Success */}
          {authStatus === 'success' && (
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                <CheckCircle className="w-10 h-10 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Authentication Successful!
              </h3>
              <p className="text-gray-600">
                Redirecting to the app...
              </p>
            </div>
          )}

          {/* Error */}
          {authStatus === 'error' && (
            <div className="space-y-4">
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-red-900 mb-2">
                      Authentication Failed
                    </h3>
                    <p className="text-sm text-red-700 whitespace-pre-line">
                      {errorMessage}
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={() => {
                  setAuthStatus('checking');
                  checkAuthStatus();
                }}
                className="w-full bg-gray-200 text-gray-700 py-3 px-6 rounded-lg font-semibold hover:bg-gray-300 transition-all duration-200"
              >
                Try Again
              </button>

              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-700 mb-2 font-medium">
                  Troubleshooting:
                </p>
                <ul className="text-xs text-gray-600 space-y-1">
                  <li>• Make sure backend is running: <code className="bg-gray-200 px-1 rounded">npm run start:backend</code></li>
                  <li>• Check <code className="bg-gray-200 px-1 rounded">backend/credentials/client_secret.json</code> exists</li>
                  <li>• Verify OAuth client type is "Desktop app" in Google Cloud Console</li>
                  <li>• Try deleting <code className="bg-gray-200 px-1 rounded">backend/credentials/token.json</code> and retry</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-8 pt-6 border-t border-gray-200 text-center">
          <p className="text-xs text-gray-500">
            Powered by Ollama • Privacy-first AI
          </p>
        </div>
      </div>
    </div>
  );
};

export default AuthSplash;

