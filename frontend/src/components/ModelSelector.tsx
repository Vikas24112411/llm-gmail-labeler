import React, { useState, useEffect } from 'react';
import { ChevronDown, Cpu, Loader2 } from 'lucide-react';

interface ModelSelectorProps {
  selectedModel: string;
  onModelChange: (model: string) => void;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  selectedModel,
  onModelChange,
}) => {
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    fetchModels();
  }, []);

  const fetchModels = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8502/api/models');
      const data = await response.json();
      setModels(data.models || ['gemma3:4b']);
    } catch (error) {
      console.error('Failed to fetch models:', error);
      setModels(['gemma3:4b']); // Fallback to default model
    } finally {
      setLoading(false);
    }
  };

  const handleModelSelect = (model: string) => {
    onModelChange(model);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        disabled={loading}
      >
        <Cpu size={16} className="text-gray-600" />
        <span className="text-sm font-medium text-gray-700 truncate max-w-32">
          {selectedModel}
        </span>
        {loading ? (
          <Loader2 size={14} className="text-gray-400 animate-spin" />
        ) : (
          <ChevronDown size={14} className="text-gray-400" />
        )}
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-60 overflow-y-auto">
            <div className="p-2">
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                Available Models
              </div>
              
              {models.length === 0 ? (
                <div className="text-sm text-gray-500 py-2">
                  No models found
                </div>
              ) : (
                <div className="space-y-1">
                  {models.map((model) => (
                    <button
                      key={model}
                      onClick={() => handleModelSelect(model)}
                      className={`w-full text-left px-3 py-2 text-sm rounded-md transition-colors ${
                        model === selectedModel
                          ? 'bg-blue-50 text-blue-700 font-medium'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Cpu size={14} className="text-gray-400" />
                        <span className="truncate">{model}</span>
                        {model === selectedModel && (
                          <div className="ml-auto w-2 h-2 bg-blue-600 rounded-full" />
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
              
              <div className="border-t border-gray-100 mt-2 pt-2">
                <button
                  onClick={fetchModels}
                  className="w-full text-left px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-md transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Loader2 size={14} />
                    Refresh Models
                  </div>
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
