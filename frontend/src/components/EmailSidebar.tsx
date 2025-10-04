import React from 'react';
import { Label } from '../types/email';
import { Inbox, Tag } from 'lucide-react';

interface EmailSidebarProps {
  labels: Label[];
  selectedLabel: string | null;
  onLabelSelect: (labelId: string | null) => void;
  unreadCount: number;
}

export const EmailSidebar: React.FC<EmailSidebarProps> = ({
  labels,
  selectedLabel,
  onLabelSelect,
  unreadCount,
}) => {
  return (
    <div className="w-64 bg-white border-r border-gray-200 flex flex-col h-full overflow-hidden">
      {/* Sidebar content */}
      <div className="p-4">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Gmail Labeler</h2>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2">
        <button
          onClick={() => onLabelSelect(null)}
          className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg mb-1 transition-colors ${
            selectedLabel === null
              ? 'bg-blue-50 text-blue-600'
              : 'text-gray-700 hover:bg-gray-100'
          }`}
        >
          <Inbox size={20} />
          <span className="flex-1 text-left font-medium">Inbox</span>
          {unreadCount > 0 && (
            <span className="text-xs bg-blue-600 text-white px-2 py-0.5 rounded-full">
              {unreadCount}
            </span>
          )}
        </button>

        <div className="mt-4 mb-2 px-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase">
            <Tag size={14} />
            <span>Labels</span>
          </div>
        </div>

        {labels.map((label) => (
          <button
            key={label.id}
            onClick={() => onLabelSelect(label.id)}
            className={`w-full flex items-center gap-3 px-4 py-2 rounded-lg mb-1 transition-colors ${
              selectedLabel === label.id
                ? 'bg-blue-50 text-blue-600'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: label.color || '#6b7280' }}
            />
            <span className="flex-1 text-left text-sm">{label.name}</span>
          </button>
        ))}
      </nav>

    </div>
  );
};

