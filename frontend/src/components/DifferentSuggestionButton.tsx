import React from 'react';
import { RefreshCw } from 'lucide-react';

interface DifferentSuggestionButtonProps {
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  title?: string;
}

export const DifferentSuggestionButton: React.FC<DifferentSuggestionButtonProps> = ({
  onClick,
  disabled = false,
  loading = false,
  className = "",
  title = "Get a different suggestion"
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      title={title}
      className={`
        flex items-center justify-center w-6 h-6 rounded-md transition-all duration-200
        bg-orange-50 hover:bg-orange-100 border border-orange-200 hover:border-orange-300
        text-orange-700 shadow-sm hover:shadow-md
        disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
        active:scale-95 transform
        ${className}
      `}
    >
      <RefreshCw 
        size={14} 
        className={`${loading ? 'animate-spin' : ''}`}
      />
    </button>
  );
};
