import React, { memo, useState } from 'react';
import { Email } from '../types/email';
import { Star, StarOff, Loader2, Check, X, MessageCircle, Send } from 'lucide-react';
import { GeminiButton } from './GeminiButton';
import { DifferentSuggestionButton } from './DifferentSuggestionButton';

interface EmailListItemProps {
  email: Email;
  selected: boolean;
  onSelect: (id: string) => void;
  onToggleSelect: (id: string, checked: boolean) => void;
  onToggleStar: (id: string) => void;
  onGetSuggestions: (id: string) => void;
  onGetDifferentSuggestion: (id: string) => void;
  onAcceptSuggestion: (id: string, label: string) => void;
  onRejectSuggestions: (id: string) => void;
  onSendMessage: (id: string, message: string) => void;
}

export const EmailListItem = memo<EmailListItemProps>(({
  email,
  selected,
  onSelect,
  onToggleSelect,
  onToggleStar,
  onGetSuggestions,
  onGetDifferentSuggestion,
  onAcceptSuggestion,
  onRejectSuggestions,
  onSendMessage,
}) => {
  const [showChatInput, setShowChatInput] = useState(false);
  const [chatMessage, setChatMessage] = useState('');

  const handleSendMessage = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (chatMessage.trim()) {
      onSendMessage(email.id, chatMessage.trim());
      setChatMessage('');
      setShowChatInput(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);

    if (hours < 1) return 'just now';
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div
      className={`border-b border-gray-200 px-4 py-3 hover:bg-gray-50 transition-colors cursor-pointer ${
        !email.read ? 'bg-blue-50/30' : ''
      } ${selected ? 'bg-blue-100' : ''}`}
    >
      <div className="flex items-start gap-3">
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => {
            e.stopPropagation();
            onToggleSelect(email.id, e.target.checked);
          }}
          className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
        />

        {/* Star */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleStar(email.id);
          }}
          className="mt-1 text-gray-400 hover:text-yellow-500 transition-colors"
        >
          {email.starred ? <Star size={18} fill="currentColor" /> : <StarOff size={18} />}
        </button>

        {/* Email content */}
        <div className="flex-1 min-w-0" onClick={() => onSelect(email.id)}>
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-sm ${!email.read ? 'font-semibold' : 'font-normal'} text-gray-900 truncate`}>
              {email.from}
            </span>
            <span className="text-xs text-gray-500 flex-shrink-0">{formatDate(email.date)}</span>
          </div>

          <div className={`text-sm ${!email.read ? 'font-semibold' : 'font-normal'} text-gray-900 mb-1 truncate`}>
            {email.subject}
          </div>

          <div className="text-sm text-gray-600 truncate">{email.snippet}</div>

          {/* Existing Labels */}
          {email.labels.length > 0 && (
            <div className="mt-2">
              <div className="text-xs text-gray-500 mb-1">Applied labels:</div>
              <div className="flex flex-wrap gap-1">
                {email.labels.map((label, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 text-xs bg-green-100 text-green-800 border border-green-200 rounded-full font-medium"
                  >
                    ✓ {label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Suggestions */}
          {email.suggestionsLoading && (
            <div className="flex items-center gap-2 mt-2 text-sm text-blue-600">
              <Loader2 size={16} className="animate-spin" />
              <span>Getting suggestions...</span>
            </div>
          )}

          {email.suggestions && email.suggestions.length > 0 && (
            <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="text-xs text-blue-600 mb-2 font-medium">💡 AI Suggestions:</div>
              <div className="flex flex-wrap gap-2">
                {email.suggestions.map((suggestion, idx) => (
                  <div key={idx} className="flex items-center gap-1.5 bg-white px-2 py-1 rounded-md border border-blue-300">
                    <span className="text-sm text-blue-800">{suggestion}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAcceptSuggestion(email.id, suggestion);
                      }}
                      className="flex items-center justify-center w-6 h-6 rounded-md transition-all duration-200 bg-green-50 hover:bg-green-100 border border-green-200 hover:border-green-300 text-green-700 shadow-sm hover:shadow-md active:scale-95 transform"
                      title="Accept suggestion"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRejectSuggestions(email.id);
                      }}
                      className="flex items-center justify-center w-6 h-6 rounded-md transition-all duration-200 bg-red-50 hover:bg-red-100 border border-red-200 hover:border-red-300 text-red-700 shadow-sm hover:shadow-md active:scale-95 transform"
                      title="Reject suggestions"
                    >
                      <X size={14} />
                    </button>
                    <DifferentSuggestionButton
                      onClick={(e) => {
                        e.stopPropagation();
                        // If there's a chat message, use it for context
                        if (chatMessage.trim()) {
                          // First reject current suggestions, then send message for regeneration
                          if (email.suggestions && email.suggestions.length > 0) {
                            onRejectSuggestions(email.id);
                          }
                          onSendMessage(email.id, chatMessage.trim());
                        } else {
                          onGetDifferentSuggestion(email.id);
                        }
                      }}
                      loading={email.suggestionsLoading}
                      title="Get a different suggestion for this email"
                    />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowChatInput(!showChatInput);
                      }}
                      className="flex items-center justify-center w-6 h-6 rounded-md transition-all duration-200 bg-blue-50 hover:bg-blue-100 border border-blue-200 hover:border-blue-300 text-blue-700 shadow-sm hover:shadow-md active:scale-95 transform"
                      title="Add context for better suggestions"
                    >
                      <MessageCircle size={14} />
                    </button>
                  </div>
                ))}
              </div>
              
              {/* Chat Input Area */}
              {showChatInput && (
                <div className="mt-3 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={chatMessage}
                      onChange={(e) => setChatMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Enter message"
                      className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={(e) => handleSendMessage(e)}
                      disabled={!chatMessage.trim()}
                      className="flex items-center justify-center w-8 h-8 rounded-md transition-all duration-200 bg-blue-500 hover:bg-blue-600 text-white shadow-sm hover:shadow-md active:scale-95 transform disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Send message"
                    >
                      <Send size={14} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Get suggestions button */}
        {!email.suggestions && !email.suggestionsLoading && (
          <GeminiButton
            onClick={(e) => {
              e.stopPropagation();
              onGetSuggestions(email.id);
            }}
            loading={email.suggestionsLoading}
            title={email.labels.length > 0 ? "Get additional label suggestions" : "Get AI label suggestions"}
          />
        )}
      </div>
    </div>
  );
});

EmailListItem.displayName = 'EmailListItem';

