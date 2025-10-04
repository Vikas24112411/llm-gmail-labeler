import React from 'react';

interface PageSizeSettingsProps {
  pageSize: number;
  onPageSizeChange: (newPageSize: number) => void;
}

export const PageSizeSettings: React.FC<PageSizeSettingsProps> = ({
  pageSize,
  onPageSizeChange,
}) => {
  const pageSizeOptions = [5, 10, 20, 50];

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="page-size-select" className="text-sm text-gray-600 whitespace-nowrap">
        Per page:
      </label>
      <select
        id="page-size-select"
        value={pageSize}
        onChange={(e) => onPageSizeChange(parseInt(e.target.value))}
        className="px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-transparent bg-white"
      >
        {pageSizeOptions.map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </select>
    </div>
  );
};
