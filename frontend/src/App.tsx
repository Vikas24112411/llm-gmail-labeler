import React, { useState, useMemo } from 'react';
import { Search, Menu, RefreshCw, Loader2 } from 'lucide-react';
import { EmailSidebar } from './components/EmailSidebar';
import { EmailListItem } from './components/EmailListItem';
import { EmailDetail } from './components/EmailDetail';
import { PaginationControls } from './components/PaginationControls';
import { ThresholdSettings } from './components/ThresholdSettings';
import { PageSizeSettings } from './components/PageSizeSettings';
import { useGmailData } from './hooks/useGmailData';
import { Email } from './types/email';

export default function App() {
  const {
    emails,
    labels,
    loading,
    error,
    currentPage,
    pageSize,
    pagination,
    threshold,
    setThreshold,
    handlePageSizeChange,
    fetchEmails,
    addLabel,
    removeLabel,
    getSuggestions,
    getDifferentSuggestion,
    acceptSuggestion,
    rejectSuggestions,
    sendMessage,
    toggleStar,
    markAsRead,
    goToNextPage,
    goToPreviousPage,
  } = useGmailData();
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [selectedEmailIds, setSelectedEmailIds] = useState<Set<string>>(new Set());
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEmails = useMemo(() => {
    return emails.filter((email) => {
      const matchesSearch =
        searchQuery === '' ||
        email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
        email.from.toLowerCase().includes(searchQuery.toLowerCase()) ||
        email.snippet.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesLabel =
        selectedLabel === null ||
        email.labels.includes(labels.find((l) => l.id === selectedLabel)?.name || '');

      return matchesSearch && matchesLabel;
    });
  }, [emails, searchQuery, selectedLabel, labels]);

  const selectedEmail = emails.find((e) => e.id === selectedEmailId);
  const unreadCount = emails.filter((e) => !e.read).length;

  const handleToggleSelect = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedEmailIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedEmailIds(newSelected);
  };

  const handleToggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedEmailIds(new Set(filteredEmails.map((e) => e.id)));
    } else {
      setSelectedEmailIds(new Set());
    }
  };

  const handleToggleStar = (id: string) => {
    toggleStar(id);
  };

  const handleAddLabel = async (emailId: string, labelName: string) => {
    try {
      await addLabel(emailId, labelName);
    } catch (err) {
      console.error('Failed to add label:', err);
    }
  };

  const handleRemoveLabel = async (emailId: string, labelName: string) => {
    try {
      await removeLabel(emailId, labelName);
    } catch (err) {
      console.error('Failed to remove label:', err);
    }
  };

  const handleGetSuggestions = (emailId: string) => {
    getSuggestions(emailId);
  };

  const handleAcceptSuggestion = (emailId: string, labelName: string) => {
    acceptSuggestion(emailId, labelName);
  };

  const handleRejectSuggestions = (emailId: string) => {
    rejectSuggestions(emailId);
  };

  const handleGetLLMSuggestions = (email: Email) => {
    getSuggestions(email.id);
  };

  const handleSelectEmail = (id: string) => {
    setSelectedEmailId(id);
    markAsRead(id);
  };

  const handleRefresh = () => {
    fetchEmails();
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-4 flex-shrink-0">
        <button className="lg:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <Menu size={20} />
        </button>
        
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center text-white font-bold">
            G
          </div>
          <span className="text-gray-700 font-semibold">LLM Gmail Labeler</span>
        </div>
        
        <div className="flex-1 max-w-2xl">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search mail"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-100 border border-transparent rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
            />
          </div>
        </div>
        
        <button 
          onClick={handleRefresh}
          disabled={loading}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw size={20} className={`text-gray-700 ${loading ? 'animate-spin' : ''}`} />
        </button>
        
        {/* Page Size Settings */}
        <div className="flex items-center gap-2">
          <PageSizeSettings
            pageSize={pageSize}
            onPageSizeChange={handlePageSizeChange}
          />
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col">
          <EmailSidebar
            labels={labels}
            selectedLabel={selectedLabel}
            onLabelSelect={setSelectedLabel}
            unreadCount={unreadCount}
          />
          
          {/* Threshold Settings */}
          <div className="p-4 border-t border-gray-200">
            <ThresholdSettings
              threshold={threshold}
              onThresholdChange={setThreshold}
            />
          </div>
        </div>

        {/* Email List */}
        {!selectedEmail && (
          <div className="flex-1 bg-white overflow-y-auto pb-20">
            {/* Error message */}
            {error && (
              <div className="m-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                <p className="font-medium">Error loading emails</p>
                <p className="text-sm mt-1">{error}</p>
                <button
                  onClick={handleRefresh}
                  className="mt-2 px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                >
                  Retry
                </button>
              </div>
            )}

            <div className="border-b border-gray-200 p-2 flex items-center gap-2 bg-gray-50">
              <input
                type="checkbox"
                checked={selectedEmailIds.size === filteredEmails.length && filteredEmails.length > 0}
                onChange={(e) => handleToggleSelectAll(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
              />
              {selectedEmailIds.size > 0 && (
                <span className="text-sm text-gray-600">
                  {selectedEmailIds.size} selected
                </span>
              )}
              {loading && (
                <div className="flex items-center gap-2 text-sm text-gray-600 ml-auto">
                  <Loader2 size={16} className="animate-spin" />
                  <span>Loading emails...</span>
                </div>
              )}
            </div>
            
            <div>
              {filteredEmails.map((email) => (
                <EmailListItem
                  key={email.id}
                  email={email}
                  selected={selectedEmailIds.has(email.id)}
                  onSelect={handleSelectEmail}
                  onToggleSelect={handleToggleSelect}
                  onToggleStar={handleToggleStar}
                  onGetSuggestions={handleGetSuggestions}
                  onGetDifferentSuggestion={getDifferentSuggestion}
                  onAcceptSuggestion={handleAcceptSuggestion}
                  onRejectSuggestions={handleRejectSuggestions}
                  onSendMessage={sendMessage}
                />
              ))}
            </div>
            
            {!loading && filteredEmails.length === 0 && !error && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-lg mb-2">No emails found</p>
                <button
                  onClick={handleRefresh}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Fetch Emails
                </button>
              </div>
            )}
            
            {/* Pagination Controls */}
            {pagination && (
              <PaginationControls
                currentPage={currentPage}
                pagination={pagination}
                onNextPage={goToNextPage}
                onPreviousPage={goToPreviousPage}
                loading={loading}
              />
            )}
          </div>
        )}

        {/* Email Detail */}
        {selectedEmail && (
          <EmailDetail
            email={selectedEmail}
            labels={labels}
            onBack={() => setSelectedEmailId(null)}
            onToggleStar={handleToggleStar}
            onAddLabel={handleAddLabel}
            onRemoveLabel={handleRemoveLabel}
            onGetLLMSuggestions={handleGetLLMSuggestions}
            llmSuggestions={selectedEmail.suggestions || []}
          />
        )}
      </div>
    </div>
  );
}
