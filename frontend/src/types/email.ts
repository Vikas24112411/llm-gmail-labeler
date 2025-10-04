export interface Email {
  id: string;
  threadId: string;
  from: string;
  to: string;
  subject: string;
  date: string;
  snippet: string;
  body?: string;
  labelIds: string[];
  labels: string[];
  read: boolean;
  starred: boolean;
  suggestions?: string[];
  suggestionsLoading?: boolean;
}

export interface Label {
  id: string;
  name: string;
  type: string;
  color?: string;
}

export interface LabelSuggestion {
  email: Email;
  suggestedLabel: string;
  confidence: number;
  rationale: string;
  source: 'llm' | 'memory' | 'embedding';
  scores?: Record<string, number>;
}

