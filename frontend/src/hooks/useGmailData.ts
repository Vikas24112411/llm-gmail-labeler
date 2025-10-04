import { useState, useEffect, useCallback } from 'react';
import { Email, Label } from '../types/email';
import { emailAPI, labelAPI, suggestionAPI } from '../services/api';

export const useGmailData = () => {
  const [emails, setEmails] = useState<Email[]>([]);
  const [labels, setLabels] = useState<Label[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10); // Default page size
  const [pagination, setPagination] = useState<any>({});
  const [threshold, setThreshold] = useState(0.3); // Default threshold
  const [rejectedSuggestions, setRejectedSuggestions] = useState<Map<string, string[]>>(new Map()); // Track rejected suggestions per email
  const [userMessages, setUserMessages] = useState<Map<string, string[]>>(new Map()); // Track user messages per email

  // Fetch emails from API with pagination
  const fetchEmails = useCallback(async (maxResults: number = 10, page: number = currentPage, pageSizeParam: number = pageSize) => {
    setLoading(true);
    setError(null);
    try {
      const response = await emailAPI.fetchEmails(maxResults, page, pageSizeParam);
      setEmails(response.emails);
      setPagination(response.pagination);
      setCurrentPage(page);
      
      // Clear rejected suggestions and user messages when fetching new emails
      setRejectedSuggestions(new Map());
      setUserMessages(new Map());
    } catch (err: any) {
      setError(err.message || 'Failed to fetch emails');
      console.error('Error fetching emails:', err);
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize]);

  // Fetch labels from API
  const fetchLabels = useCallback(async () => {
    try {
      const response = await labelAPI.fetchLabels();
      setLabels(response);
    } catch (err: any) {
      console.error('Error fetching labels:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchEmails();
    fetchLabels();
  }, [fetchEmails, fetchLabels]);

  // Add label to email
  const addLabel = useCallback(async (emailId: string, labelName: string) => {
    try {
      await labelAPI.addLabel(emailId, labelName);
      
      // Update local state
      setEmails(prev => prev.map(email =>
        email.id === emailId && !email.labels.includes(labelName)
          ? { ...email, labels: [...email.labels, labelName] }
          : email
      ));
    } catch (err: any) {
      console.error('Error adding label:', err);
      throw err;
    }
  }, []);

  // Remove label from email
  const removeLabel = useCallback(async (emailId: string, labelName: string) => {
    try {
      await labelAPI.removeLabel(emailId, labelName);
      
      // Update local state
      setEmails(prev => prev.map(email =>
        email.id === emailId
          ? { ...email, labels: email.labels.filter(l => l !== labelName) }
          : email
      ));
    } catch (err: any) {
      console.error('Error removing label:', err);
      throw err;
    }
  }, []);

  // Get AI suggestions for an email
  const getSuggestions = useCallback(async (emailId: string) => {
    // Set loading state
    setEmails(prev => prev.map(email =>
      email.id === emailId
        ? { ...email, suggestionsLoading: true }
        : email
    ));

    try {
      const response = await suggestionAPI.getSuggestions(emailId, threshold);
      
      // Update with suggestions
      setEmails(prev => prev.map(email =>
        email.id === emailId
          ? {
              ...email,
              suggestions: [response.suggestedLabel],
              suggestionsLoading: false
            }
          : email
      ));
    } catch (err: any) {
      console.error('Error getting suggestions:', err);
      
      // Clear loading state on error
      setEmails(prev => prev.map(email =>
        email.id === emailId
          ? { ...email, suggestionsLoading: false }
          : email
      ));
    }
  }, [threshold]);

  // Get different AI suggestion for an email (when user doesn't like current suggestion)
  const getDifferentSuggestion = useCallback(async (emailId: string) => {
    // Set loading state
    setEmails(prev => prev.map(email =>
      email.id === emailId
        ? { ...email, suggestionsLoading: true }
        : email
    ));

    try {
      // Get current suggestions to add to rejected list
      const email = emails.find(e => e.id === emailId);
      const currentSuggestions = email?.suggestions || [];
      
      // Add current suggestions to rejected list for this email
      setRejectedSuggestions(prev => {
        const newMap = new Map(prev);
        const existingRejected = newMap.get(emailId) || [];
        const newRejected = [...existingRejected, ...currentSuggestions];
        newMap.set(emailId, newRejected);
        return newMap;
      });
      
      // Get accumulated rejected suggestions for this email
      const accumulatedRejected = rejectedSuggestions.get(emailId) || [];
      const allRejectedSuggestions = [...accumulatedRejected, ...currentSuggestions];
      
      const response = await suggestionAPI.getDifferentSuggestion(emailId, allRejectedSuggestions, threshold);
      
      // Update with new suggestions
      setEmails(prev => prev.map(email =>
        email.id === emailId
          ? {
              ...email,
              suggestions: [response.suggestedLabel],
              suggestionsLoading: false
            }
          : email
      ));
    } catch (err: any) {
      console.error('Error getting different suggestion:', err);
      
      // Clear loading state on error
      setEmails(prev => prev.map(email =>
        email.id === emailId
          ? { ...email, suggestionsLoading: false }
          : email
      ));
    }
  }, [emails, rejectedSuggestions, threshold]);

  // Get batch suggestions
  const getBatchSuggestions = useCallback(async (maxResults: number = 10) => {
    setLoading(true);
    try {
      const response = await suggestionAPI.getBatchSuggestions(maxResults);
      
      // Update emails with suggestions
      const suggestionsMap = new Map(
        response.map(s => [s.email.id, s.suggestedLabel])
      );
      
      setEmails(prev => prev.map(email => ({
        ...email,
        suggestions: suggestionsMap.has(email.id) 
          ? [suggestionsMap.get(email.id)!] 
          : email.suggestions
      })));
    } catch (err: any) {
      console.error('Error getting batch suggestions:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Accept suggestion
  const acceptSuggestion = useCallback(async (emailId: string, labelName: string) => {
    try {
      await addLabel(emailId, labelName);
      
      // Update the email to include the new label in its labels array
      setEmails(prev => prev.map(email => {
        if (email.id === emailId) {
          const newSuggestions = (email.suggestions || []).filter(s => s !== labelName);
          const existingLabels = email.labels || [];
          const updatedLabels = existingLabels.includes(labelName) 
            ? existingLabels 
            : [...existingLabels, labelName];
          return {
            ...email,
            labels: updatedLabels,
            suggestions: newSuggestions.length > 0 ? newSuggestions : undefined,
          };
        }
        return email;
      }));
      
      // Clear rejected suggestions and user messages for this email since user made a decision
      setRejectedSuggestions(prev => {
        const newMap = new Map(prev);
        newMap.delete(emailId);
        return newMap;
      });
      setUserMessages(prev => {
        const newMap = new Map(prev);
        newMap.delete(emailId);
        return newMap;
      });
    } catch (err: any) {
      console.error('Error accepting suggestion:', err);
    }
  }, [addLabel]);

  // Send message for better suggestions
  const sendMessage = useCallback(async (emailId: string, message: string) => {
    try {
      console.log(`Sending context message for email ${emailId}:`, message);
      
      // Set loading state
      setEmails(prev => prev.map(email => 
        email.id === emailId ? { ...email, suggestionsLoading: true } : email
      ));
      
      // Get accumulated user messages and rejected suggestions for this email
      const accumulatedMessages = userMessages.get(emailId) || [];
      const allUserMessages = [...accumulatedMessages, message];
      const rejectedSuggestionsList = rejectedSuggestions.get(emailId) || [];
      
      // Combine all user messages into a single context string
      const combinedContext = allUserMessages.join('; ');
      
      console.log(`📝 User message accumulation for email ${emailId}:`);
      console.log(`   - Previous messages: [${accumulatedMessages.join(', ')}]`);
      console.log(`   - New message: "${message}"`);
      console.log(`   - Combined context: "${combinedContext}"`);
      
      // Accumulate user messages for this email (update state for future calls)
      setUserMessages(prev => {
        const newMap = new Map(prev);
        newMap.set(emailId, allUserMessages);
        return newMap;
      });
      
      // Call the new API endpoint with user context
      const suggestion = await suggestionAPI.getSuggestionWithContext(
        emailId, 
        combinedContext, 
        rejectedSuggestionsList, 
        threshold
      );
      
      if (suggestion) {
        // Transform API response to match frontend interface
        const transformedSuggestion = {
          ...suggestion,
          suggestedLabel: (suggestion as any).suggested_label || suggestion.suggestedLabel
        };
        
        // Update the email with the new suggestion
        setEmails(prev => prev.map(email => {
          if (email.id === emailId) {
            return {
              ...email,
              suggestions: [transformedSuggestion.suggestedLabel],
              suggestionsLoading: false
            };
          }
          return email;
        }));
        
        console.log(`New suggestion with context: ${transformedSuggestion.suggestedLabel}`);
      }
    } catch (err: any) {
      console.error('Error sending message:', err);
      // Set loading to false in case of error
      setEmails(prev => prev.map(email => {
        if (email.id === emailId) {
          return {
            ...email,
            suggestionsLoading: false
          };
        }
        return email;
      }));
    }
  }, [threshold, rejectedSuggestions, userMessages]);

  // Reject suggestions
  const rejectSuggestions = useCallback(async (emailId: string) => {
    try {
      const email = emails.find(e => e.id === emailId);
      if (!email || !email.suggestions || email.suggestions.length === 0) {
        return;
      }

      // Send rejection to backend for each suggested label
      const rejections: { [key: string]: { approved: boolean; final_label: string } } = {};
      email.suggestions.forEach(suggestion => {
        rejections[emailId] = {
          approved: false,
          final_label: suggestion
        };
      });

      // Call backend to store rejected labels
      await suggestionAPI.applyLabels(rejections);
      
      // Remove suggestions from UI
      setEmails(prev => prev.map(email =>
        email.id === emailId
          ? { ...email, suggestions: undefined }
          : email
      ));
      
      // Clear rejected suggestions and user messages for this email since user made a decision
      setRejectedSuggestions(prev => {
        const newMap = new Map(prev);
        newMap.delete(emailId);
        return newMap;
      });
      setUserMessages(prev => {
        const newMap = new Map(prev);
        newMap.delete(emailId);
        return newMap;
      });
      
      console.log(`Rejected suggestions for email ${emailId}, stored as negative examples`);
    } catch (err: any) {
      console.error('Failed to reject suggestions:', err);
      // Still remove from UI even if backend call fails
      setEmails(prev => prev.map(email =>
        email.id === emailId
          ? { ...email, suggestions: undefined }
          : email
      ));
    }
  }, [emails]);

  // Toggle star
  const toggleStar = useCallback((emailId: string) => {
    setEmails(prev => prev.map(email =>
      email.id === emailId
        ? { ...email, starred: !email.starred }
        : email
    ));
    
    // TODO: Call API to update star status
  }, []);

  // Mark as read
  const markAsRead = useCallback((emailId: string) => {
    setEmails(prev => prev.map(email =>
      email.id === emailId
        ? { ...email, read: true }
        : email
    ));
    
    // TODO: Call API to mark as read
  }, []);

  // Handle page size change
  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setCurrentPage(1); // Reset to first page when changing page size
    fetchEmails(10, 1, newPageSize);
  }, [fetchEmails]);

  // Pagination navigation functions
  const goToNextPage = useCallback(() => {
    if (pagination.has_next_page) {
      fetchEmails(10, pagination.next_page, pageSize);
    }
  }, [pagination, fetchEmails, pageSize]);

  const goToPreviousPage = useCallback(() => {
    if (pagination.has_previous_page) {
      fetchEmails(10, pagination.previous_page, pageSize);
    }
  }, [pagination, fetchEmails, pageSize]);

  const goToPage = useCallback((page: number) => {
    fetchEmails(10, page, pageSize);
  }, [fetchEmails, pageSize]);

  return {
    emails,
    labels,
    loading,
    error,
    currentPage,
    pageSize,
    pagination,
    fetchEmails,
    fetchLabels,
    addLabel,
    removeLabel,
    getSuggestions,
    getDifferentSuggestion,
    getBatchSuggestions,
    acceptSuggestion,
    rejectSuggestions,
    sendMessage,
    toggleStar,
    markAsRead,
    goToNextPage,
    goToPreviousPage,
    goToPage,
    handlePageSizeChange,
    threshold,
    setThreshold,
  };
};

