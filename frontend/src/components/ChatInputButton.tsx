import React, { useState } from 'react';
import { MessageCircle, Send } from 'lucide-react';

interface ChatInputButtonProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  title?: string;
}

export const ChatInputButton: React.FC<ChatInputButtonProps> = ({
  onSendMessage,
  disabled = false,
  loading = false,
  className = "",
  title = "Add context for better suggestions"
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [message, setMessage] = useState('');

  const handleSend = () => {
    if (message.trim()) {
      onSendMessage(message.trim());
      setMessage('');
      setIsExpanded(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        disabled={disabled || loading}
        title={title}
        className={`
          flex items-center justify-center w-6 h-6 rounded-md transition-all duration-200
          bg-blue-50 hover:bg-blue-100 border border-blue-200 hover:border-blue-300
          text-blue-700 shadow-sm hover:shadow-md
          disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
          active:scale-95 transform
          ${className}
        `}
      >
        <MessageCircle size={14} />
      </button>
    );
  }

  return (
    <div className="flex items-center bg-gray-50 rounded-lg border border-gray-200 shadow-sm transition-all duration-300 ease-in-out overflow-hidden min-w-[200px]">
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyPress={handleKeyPress}
        placeholder="Enter message"
        className="flex-1 px-3 py-2 text-sm border-none outline-none bg-transparent placeholder-gray-500 text-gray-700"
        autoFocus
        disabled={loading}
      />
      <button
        onClick={handleSend}
        disabled={!message.trim() || loading}
        className="flex items-center justify-center w-8 h-8 m-1 rounded-md transition-all duration-200 bg-blue-500 hover:bg-blue-600 text-white shadow-sm hover:shadow-md active:scale-95 transform disabled:opacity-50 disabled:cursor-not-allowed"
        title="Send message"
      >
        <Send size={14} />
      </button>
    </div>
  );
};
