import type { ChatHistoryMessage, ChatResponsePayload } from '../api';

export type Role = 'user' | 'assistant';

export interface MessageEntry {
  id: string;
  role: Role;
  content: string;
  details?: ChatResponsePayload;
  timestamp: number;
}

export type HistoryConverter = (messages: ChatHistoryMessage[]) => MessageEntry[];
