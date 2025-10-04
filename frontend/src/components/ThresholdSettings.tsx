import React from 'react';
import { Settings, Brain } from 'lucide-react';

interface ThresholdSettingsProps {
  threshold: number;
  onThresholdChange: (threshold: number) => void;
}

export const ThresholdSettings: React.FC<ThresholdSettingsProps> = ({
  threshold,
  onThresholdChange,
}) => {
  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newThreshold = parseFloat(e.target.value);
    onThresholdChange(newThreshold);
  };

  const getThresholdDescription = (value: number) => {
    if (value >= 0.7) return "Very Strict - Only high-confidence matches";
    if (value >= 0.5) return "Strict - Good confidence matches";
    if (value >= 0.3) return "Balanced - Moderate confidence matches";
    return "Loose - Low confidence matches";
  };

  const getThresholdColor = (value: number) => {
    if (value >= 0.7) return "text-red-600";
    if (value >= 0.5) return "text-orange-600";
    if (value >= 0.3) return "text-yellow-600";
    return "text-green-600";
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Brain size={18} className="text-blue-600" />
        <h3 className="text-sm font-semibold text-gray-900">AI Threshold</h3>
        <Settings size={16} className="text-gray-400" />
      </div>
      
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Threshold:</span>
          <span className={`text-sm font-medium ${getThresholdColor(threshold)}`}>
            {(threshold * 100).toFixed(0)}%
          </span>
        </div>
        
        <div className="relative">
          <input
            type="range"
            min="0.1"
            max="0.9"
            step="0.05"
            value={threshold}
            onChange={handleSliderChange}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
            style={{
              background: `linear-gradient(to right, #ef4444 0%, #f97316 30%, #eab308 60%, #22c55e 100%)`
            }}
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>Loose</span>
            <span>Balanced</span>
            <span>Strict</span>
          </div>
        </div>
        
        <div className={`text-xs ${getThresholdColor(threshold)} font-medium`}>
          {getThresholdDescription(threshold)}
        </div>
      </div>
    </div>
  );
};
