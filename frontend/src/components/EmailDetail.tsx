import React, { useState, memo } from 'react';
import { Email, Label } from '../types/email';
import { ArrowLeft, Star, StarOff, Sparkles, Tag, X } from 'lucide-react';

interface EmailDetailProps {
  email: Email;
  labels: Label[];
  onBack: () => void;
  onToggleStar: (id: string) => void;
  onAddLabel: (emailId: string, labelName: string) => void;
  onRemoveLabel: (emailId: string, labelName: string) => void;
  onGetLLMSuggestions: (email: Email) => void;
  llmSuggestions: string[];
}

export const EmailDetail = memo<EmailDetailProps>(({
  email,
  labels,
  onBack,
  onToggleStar,
  onAddLabel,
  onRemoveLabel,
  onGetLLMSuggestions,
  llmSuggestions,
}) => {
  const [showLabelDropdown, setShowLabelDropdown] = useState(false);

  const availableLabels = labels.filter(
    (label) => !email.labels.includes(label.name)
  );

  return (
    <div className="flex-1 bg-white flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="border-b border-gray-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft size={20} />
            <span className="font-medium">Back to Inbox</span>
          </button>

          <button
            onClick={() => onToggleStar(email.id)}
            className="text-gray-400 hover:text-yellow-500 transition-colors"
          >
            {email.starred ? <Star size={20} fill="currentColor" /> : <StarOff size={20} />}
          </button>
        </div>

        <h1 className="text-2xl font-semibold text-gray-900 mb-2">{email.subject}</h1>

        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-600">From: {email.from}</div>
            <div className="text-sm text-gray-600">To: {email.to}</div>
            <div className="text-xs text-gray-500 mt-1">
              {new Date(email.date).toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto">
          <div className="prose max-w-none">
            {email.body || email.snippet}
          </div>
        </div>
      </div>

      {/* Actions Footer */}
      <div className="border-t border-gray-200 p-4">
        {/* Current Labels */}
        {email.labels.length > 0 && (
          <div className="mb-4">
            <div className="text-sm text-gray-600 mb-2">Current labels:</div>
            <div className="flex flex-wrap gap-2">
              {email.labels.map((label, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
                >
                  {label}
                  <button
                    onClick={() => onRemoveLabel(email.id, label)}
                    className="hover:text-blue-900 transition-colors"
                  >
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* LLM Suggestions */}
        {llmSuggestions.length > 0 && (
          <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
            <div className="flex items-center gap-2 text-sm text-purple-900 mb-2">
              <Sparkles size={16} />
              <span className="font-medium">AI Suggestions:</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {llmSuggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  onClick={() => onAddLabel(email.id, suggestion)}
                  className="px-3 py-1 bg-white text-purple-800 rounded-full text-sm border border-purple-300 hover:bg-purple-100 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={() => onGetLLMSuggestions(email)}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 transition-colors"
          >
            <Sparkles size={18} />
            <span>Get AI Suggestions</span>
          </button>

          <div className="relative">
            <button
              onClick={() => setShowLabelDropdown(!showLabelDropdown)}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              <Tag size={18} />
              <span>Add Label</span>
            </button>

            {showLabelDropdown && (
              <div className="absolute bottom-full left-0 mb-2 w-64 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto z-10">
                {availableLabels.length > 0 ? (
                  availableLabels.map((label) => (
                    <button
                      key={label.id}
                      onClick={() => {
                        onAddLabel(email.id, label.name);
                        setShowLabelDropdown(false);
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2 hover:bg-gray-50 transition-colors text-left"
                    >
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: label.color }}
                      />
                      <span className="text-sm">{label.name}</span>
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-3 text-sm text-gray-500">
                    All labels applied
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

EmailDetail.displayName = 'EmailDetail';

