import axios from 'axios';
import { Email, Label, LabelSuggestion } from '../types/email';

// Configure axios instance
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8502/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds for LLM operations
});

// Email API endpoints
export const emailAPI = {
  // Fetch unread emails with pagination
  fetchEmails: async (maxResults: number = 10, page: number = 1, pageSize: number = 10) => {
    try {
      const response = await api.get('/emails', {
        params: { 
          max_results: maxResults,
          page: page,
          page_size: pageSize
        },
      });
      return {
        emails: response.data.emails || [],
        pagination: response.data.pagination || {}
      };
    } catch (error) {
      console.error('Error fetching emails:', error);
      throw error;
    }
  },

  // Get a specific email by ID
  getEmailById: async (emailId: string): Promise<Email> => {
    try {
      const response = await api.get(`/emails/${emailId}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching email:', error);
      throw error;
    }
  },

  // Mark email as read
  markAsRead: async (emailId: string): Promise<void> => {
    try {
      await api.post(`/emails/${emailId}/read`);
    } catch (error) {
      console.error('Error marking email as read:', error);
      throw error;
    }
  },

  // Star/unstar email
  toggleStar: async (emailId: string, starred: boolean): Promise<void> => {
    try {
      await api.post(`/emails/${emailId}/star`, { starred });
    } catch (error) {
      console.error('Error toggling star:', error);
      throw error;
    }
  },
};

// Label API endpoints
export const labelAPI = {
  // Fetch all labels
  fetchLabels: async (): Promise<Label[]> => {
    try {
      const response = await api.get('/labels');
      return response.data.labels || [];
    } catch (error) {
      console.error('Error fetching labels:', error);
      throw error;
    }
  },

  // Add label to email
  addLabel: async (emailId: string, labelName: string): Promise<void> => {
    try {
      await api.post(`/emails/${emailId}/labels`, { label: labelName });
    } catch (error) {
      console.error('Error adding label:', error);
      throw error;
    }
  },

  // Remove label from email
  removeLabel: async (emailId: string, labelName: string): Promise<void> => {
    try {
      await api.delete(`/emails/${emailId}/labels/${encodeURIComponent(labelName)}`);
    } catch (error) {
      console.error('Error removing label:', error);
      throw error;
    }
  },

  // Create new label
  createLabel: async (labelName: string): Promise<Label> => {
    try {
      const response = await api.post('/labels', { name: labelName });
      return response.data.label;
    } catch (error) {
      console.error('Error creating label:', error);
      throw error;
    }
  },
};

// AI Suggestion API endpoints
export const suggestionAPI = {
  // Get label suggestions for a single email
  getSuggestions: async (emailId: string, threshold: number = 0.3): Promise<LabelSuggestion> => {
    try {
      const response = await api.post('/suggestions/single', {
        email_id: emailId,
        model: "gemma3:4b",
        score_threshold: threshold,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting suggestions:', error);
      throw error;
    }
  },

  // Get different suggestion for an email (when user doesn't like current suggestion)
  getDifferentSuggestion: async (emailId: string, rejectedSuggestions: string[], threshold: number = 0.3): Promise<LabelSuggestion> => {
    try {
      const response = await api.post('/suggestions/different', {
        email_id: emailId,
        rejected_suggestions: rejectedSuggestions,
        model: "gemma3:4b",
        score_threshold: threshold,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting different suggestion:', error);
      throw error;
    }
  },

  // Get suggestion with user context message
  getSuggestionWithContext: async (emailId: string, userMessage: string, rejectedSuggestions: string[] = [], threshold: number = 0.3): Promise<LabelSuggestion> => {
    try {
      const response = await api.post('/suggestions/with-context', {
        email_id: emailId,
        user_message: userMessage,
        rejected_suggestions: rejectedSuggestions,
        model: "gemma3:4b",
        score_threshold: threshold,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting suggestion with context:', error);
      throw error;
    }
  },

  // Get batch suggestions for multiple emails
  getBatchSuggestions: async (maxResults: number = 10): Promise<LabelSuggestion[]> => {
    try {
      const response = await api.post('/suggestions/batch', {
        max_results: maxResults,
      });
      return response.data.suggestions || [];
    } catch (error) {
      console.error('Error getting batch suggestions:', error);
      throw error;
    }
  },

  // Apply approved labels
  applyLabels: async (approvals: Record<string, { approved: boolean; final_label: string }>): Promise<any> => {
    try {
      const response = await api.post('/suggestions/apply', {
        approvals,
      });
      return response.data;
    } catch (error) {
      console.error('Error applying labels:', error);
      throw error;
    }
  },
};

// Settings API
export const settingsAPI = {
  // Get current settings
  getSettings: async (): Promise<any> => {
    try {
      const response = await api.get('/settings');
      return response.data;
    } catch (error) {
      console.error('Error fetching settings:', error);
      throw error;
    }
  },

  // Update settings
  updateSettings: async (settings: any): Promise<void> => {
    try {
      await api.post('/settings', settings);
    } catch (error) {
      console.error('Error updating settings:', error);
      throw error;
    }
  },

  // Get available Ollama models
  getModels: async (): Promise<string[]> => {
    try {
      const response = await api.get('/models');
      return response.data.models || [];
    } catch (error) {
      console.error('Error fetching models:', error);
      return ['gemma3:4b']; // Fallback
    }
  },
};

// Authentication API
export const authAPI = {
  // Check authentication status
  checkAuth: async (): Promise<boolean> => {
    try {
      const response = await api.get('/auth/status');
      return response.data.authenticated || false;
    } catch (error) {
      return false;
    }
  },

  // Trigger Gmail OAuth
  authenticate: async (): Promise<{ url?: string; success: boolean }> => {
    try {
      const response = await api.post('/auth/gmail');
      return response.data;
    } catch (error) {
      console.error('Error authenticating:', error);
      throw error;
    }
  },
};

// Statistics API
export const statsAPI = {
  // Get memory statistics
  getStats: async (): Promise<any> => {
    try {
      const response = await api.get('/stats');
      return response.data;
    } catch (error) {
      console.error('Error fetching stats:', error);
      throw error;
    }
  },
};

export default api;

