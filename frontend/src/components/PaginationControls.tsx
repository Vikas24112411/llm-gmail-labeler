import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationControlsProps {
  currentPage: number;
  pagination: {
    has_next_page: boolean;
    has_previous_page: boolean;
    next_page?: number;
    previous_page?: number;
    total_emails: number;
    page_size: number;
  };
  onNextPage: () => void;
  onPreviousPage: () => void;
  loading?: boolean;
}

export const PaginationControls: React.FC<PaginationControlsProps> = ({
  currentPage,
  pagination,
  onNextPage,
  onPreviousPage,
  loading = false,
}) => {
  const startItem = (currentPage - 1) * pagination.page_size + 1;
  const endItem = Math.min(currentPage * pagination.page_size, pagination.total_emails);

  return (
    <div className="fixed bottom-4 left-1/2 transform -translate-x-1/2 z-50">
      <div className="flex items-center justify-between px-6 py-3 bg-white rounded-lg shadow-lg border border-gray-200 backdrop-blur-sm">
        <div className="flex items-center text-sm text-gray-700">
          <span>
            Showing {startItem}-{endItem} of {pagination.total_emails} emails
          </span>
        </div>
        
        <div className="flex items-center space-x-2 ml-6">
          <button
            onClick={onPreviousPage}
            disabled={!pagination.has_previous_page || loading}
            className={`flex items-center px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              !pagination.has_previous_page || loading
                ? 'text-gray-400 cursor-not-allowed'
                : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
            }`}
          >
            <ChevronLeft size={16} className="mr-1" />
            Previous
          </button>
          
          <div className="flex items-center space-x-1">
            <span className="px-3 py-1 text-sm font-medium text-gray-700 bg-gray-100 rounded-md">
              {currentPage}
            </span>
          </div>
          
          <button
            onClick={onNextPage}
            disabled={!pagination.has_next_page || loading}
            className={`flex items-center px-3 py-1 text-sm font-medium rounded-md transition-colors ${
              !pagination.has_next_page || loading
                ? 'text-gray-400 cursor-not-allowed'
                : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
            }`}
          >
            Next
            <ChevronRight size={16} className="ml-1" />
          </button>
        </div>
      </div>
    </div>
  );
};
