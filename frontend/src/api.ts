export interface VoicePlan {
  text: string;
  speakerUuid: string;
  styleId: number;
  speedScale: number;
  volumeScale: number;
  pitchScale: number;
  intonationScale: number;
  prePhonemeLength: number;
  postPhonemeLength: number;
  outputSamplingRate: number;
  prosodyDetail: unknown[];
}

export interface ChatResponsePayload {
  voice_plan?: VoicePlan | null;
  audio_path?: string | null;
  played_audio: boolean;
  raw_response?: Record<string, unknown> | null;
}

export type ChatRole = 'user' | 'assistant' | 'system';

export interface ChatHistoryMessage {
  role: ChatRole | string;
  content: string;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatHistoryMessage[];
}

export type TodoStatus = 'pending' | 'in_progress' | 'done';

export interface TodoItem {
  id: number;
  title: string;
  description: string;
  status: TodoStatus;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface TodoCreatePayload {
  title: string;
  description?: string;
  due_date?: string | null;
  status?: TodoStatus;
}

export interface TodoUpdatePayload {
  title?: string;
  description?: string | null;
  due_date?: string | null;
  status?: TodoStatus;
}

export async function postChatMessage(
  message: string,
  playAudio: boolean,
  model?: string,
): Promise<ChatResponsePayload> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, play_audio: playAudio, model }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `API request failed with status ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  const payload = (await response.json()) as ChatResponsePayload;
  return payload;
}

export async function getAvailableModels(): Promise<string[]> {
  const response = await fetch('/api/models', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `API request failed with status ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  const payload = (await response.json()) as { models: string[] };
  return payload.models;
}

export interface ProactiveChatStatus {
  enabled: boolean;
  running: boolean;
  interval_seconds: number;
  pending_count: number;
}

export interface ProactiveChatMessage {
  text: string;
  timestamp: number;
  details?: ChatResponsePayload | null;
  prompt?: string | null;
  error?: boolean;
}

export async function toggleProactiveChat(enabled: boolean): Promise<void> {
  const response = await fetch('/api/proactive-chat/toggle', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ enabled }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to toggle proactive chat: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }
}

export async function getProactiveChatStatus(): Promise<ProactiveChatStatus> {
  const response = await fetch('/api/proactive-chat/status', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to get proactive chat status: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as ProactiveChatStatus;
}

export async function getPendingProactiveMessages(): Promise<ProactiveChatMessage[]> {
  const response = await fetch('/api/proactive-chat/pending', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to get pending messages: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  const payload = (await response.json()) as { messages: ProactiveChatMessage[] };
  return payload.messages;
}

export async function getTodos(): Promise<TodoItem[]> {
  const response = await fetch('/api/todos', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to fetch todos: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as TodoItem[];
}

export async function createTodo(payload: TodoCreatePayload): Promise<TodoItem> {
  const response = await fetch('/api/todos', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to create todo: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as TodoItem;
}

export async function updateTodo(
  todoId: number,
  payload: TodoUpdatePayload,
): Promise<TodoItem> {
  const response = await fetch(`/api/todos/${todoId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to update todo: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as TodoItem;
}

export async function deleteTodo(todoId: number): Promise<void> {
  const response = await fetch(`/api/todos/${todoId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to delete todo: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }
}

export async function getChatSessions(params?: {
  limit?: number;
  query?: string;
}): Promise<ChatSessionSummary[]> {
  const searchParams = new URLSearchParams();
  if (params?.limit) {
    searchParams.set('limit', params.limit.toString());
  }
  if (params?.query) {
    searchParams.set('query', params.query);
  }
  const queryString = searchParams.toString();
  const response = await fetch(`/api/chat/sessions${queryString ? `?${queryString}` : ''}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to fetch chat sessions: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as ChatSessionSummary[];
}

export async function getChatSession(sessionId: string): Promise<ChatSessionDetail> {
  const response = await fetch(`/api/chat/sessions/${sessionId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to fetch chat session: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as ChatSessionDetail;
}

export async function getCurrentChatSession(): Promise<ChatSessionDetail> {
  const response = await fetch('/api/chat/session/current', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to fetch current session: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as ChatSessionDetail;
}

export async function loadChatSession(sessionId: string): Promise<ChatSessionDetail> {
  const response = await fetch('/api/chat/load', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_id: sessionId }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to load chat session: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as ChatSessionDetail;
}

export async function resetChatSession(): Promise<ChatSessionDetail> {
  const response = await fetch('/api/chat/reset', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `Failed to reset chat session: ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  return (await response.json()) as ChatSessionDetail;
}
