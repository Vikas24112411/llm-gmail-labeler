import React from 'react';

interface GeminiButtonProps {
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  title?: string;
}

export const GeminiButton: React.FC<GeminiButtonProps> = ({
  onClick,
  disabled = false,
  loading = false,
  className = "",
  title = "Get AI Suggestions"
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      title={title}
      className={`
        relative px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200
        bg-white hover:bg-gray-50 border border-gray-200 hover:border-gray-300
        text-gray-700 shadow-sm hover:shadow-md
        disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
        active:scale-95 transform
        ${className}
      `}
    >
      <div className="flex items-center gap-2">
        {/* Gradient Star Icon */}
        <div className="relative w-4 h-4">
          <div 
            className="w-4 h-4 rounded-sm transform rotate-45"
            style={{
              background: 'linear-gradient(45deg, #ff0000 0%, #ff8000 25%, #0080ff 50%, #00ff80 75%, #ffff00 100%)',
              clipPath: 'polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)'
            }}
          />
          {loading && (
            <div className="absolute inset-0 w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin"></div>
          )}
        </div>
        
               {/* Button Text - Removed as per user request */}
      </div>
      
      {/* Shine effect */}
      <div className="absolute inset-0 rounded-lg bg-gradient-to-r from-transparent via-white/30 to-transparent opacity-0 hover:opacity-100 transition-opacity duration-300"></div>
    </button>
  );
};
