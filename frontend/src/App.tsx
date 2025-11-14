import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import {
  ChatSessionDetail,
  ChatSessionSummary,
  TodoItem,
  TodoStatus,
  createTodo,
  getAvailableModels,
  getChatSessions,
  getCurrentChatSession,
  getPendingProactiveMessages,
  getTodos,
  getProactiveChatStatus,
  loadChatSession,
  resetChatSession,
  updateTodo,
  deleteTodo,
  postChatMessage,
  toggleProactiveChat,
} from './api';
import { SessionSidebar } from './components/SessionSidebar';
import { TodoPanel } from './components/TodoPanel';
import {
  convertHistoryMessages,
  createId,
  formatTimestamp,
} from './utils/chat';
import type { MessageEntry, Role } from './types/chat';

const statusLabels: Record<TodoStatus, string> = {
  pending: '未着手',
  in_progress: '進行中',
  done: '完了',
};

const statusOptions: TodoStatus[] = ['pending', 'in_progress', 'done'];

export default function App(): JSX.Element {
  const [messages, setMessages] = useState<MessageEntry[]>([]);
  const [sessionSummaries, setSessionSummaries] = useState<ChatSessionSummary[]>([]);
  const [sessionSearch, setSessionSearch] = useState('');
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [currentSessionTitle, setCurrentSessionTitle] = useState('新規セッション');
  const [currentSessionLoading, setCurrentSessionLoading] = useState(false);
  const [input, setInput] = useState('');
  const [playAudio, setPlayAudio] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [proactiveChatEnabled, setProactiveChatEnabled] = useState(false);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [todoLoading, setTodoLoading] = useState(false);
  const [todoError, setTodoError] = useState<string | null>(null);
  const [updatingTodoIds, setUpdatingTodoIds] = useState<Set<number>>(new Set());
  const [todoForm, setTodoForm] = useState<{
    title: string;
    description: string;
    dueDate: string;
    status: TodoStatus;
  }>({
    title: '',
    description: '',
    dueDate: '',
    status: 'pending',
  });
  const handleTodoFormChange = useCallback((updates: Partial<typeof todoForm>) => {
    setTodoForm(prev => ({ ...prev, ...updates }));
  }, [setTodoForm]);

  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => a.timestamp - b.timestamp),
    [messages],
  );

  const applySessionDetail = useCallback((session: ChatSessionDetail) => {
    setCurrentSessionId(session.session_id);
    setCurrentSessionTitle(session.title || '未命名のセッション');
    setMessages(convertHistoryMessages(session.messages));
  }, []);

  const refreshSessions = useCallback(async (query?: string) => {
    setSessionsLoading(true);
    try {
      const keyword = query?.trim() ? query.trim() : undefined;
      const data = await getChatSessions({ limit: 20, query: keyword });
      setSessionSummaries(data);
      setSessionError(null);
    } catch (err) {
      console.error('Failed to fetch chat sessions:', err);
      const message =
        err instanceof Error ? err.message : 'チャット履歴の取得に失敗しました。';
      setSessionError(message);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const loadCurrentSession = useCallback(async () => {
    setCurrentSessionLoading(true);
    try {
      const session = await getCurrentChatSession();
      applySessionDetail(session);
      setSessionError(null);
    } catch (err) {
      console.error('Failed to load current session:', err);
      const message =
        err instanceof Error ? err.message : '現在のセッション取得に失敗しました。';
      setSessionError(message);
    } finally {
      setCurrentSessionLoading(false);
    }
  }, [applySessionDetail]);

  // モデル一覧を取得
  useEffect(() => {
    async function fetchModels() {
      try {
        const models = await getAvailableModels();
        setAvailableModels(models);
        if (models.length > 0 && !selectedModel) {
          setSelectedModel(models[0]);
        }
      } catch (err) {
        console.error('Failed to fetch models:', err);
      }
    }
    fetchModels();
  }, []);

  useEffect(() => {
    loadCurrentSession();
    refreshSessions();
  }, [loadCurrentSession, refreshSessions]);

  // 能動会話の状態を初期化（ローカルストレージから復元）
  useEffect(() => {
    async function initProactiveChat() {
      try {
        const savedEnabled = localStorage.getItem('proactiveChatEnabled');
        const initialEnabled = savedEnabled === 'true';
        setProactiveChatEnabled(initialEnabled);

        // サーバー側の状態を確認
        const status = await getProactiveChatStatus();
        if (status.enabled !== initialEnabled) {
          // ローカルとサーバーの状態が一致しない場合は同期
          await toggleProactiveChat(initialEnabled);
        }
      } catch (err) {
        console.error('Failed to initialize proactive chat:', err);
      }
    }
    initProactiveChat();
  }, []);

  const refreshTodos = useCallback(async () => {
    setTodoLoading(true);
    try {
      const data = await getTodos();
      setTodos(data);
      setTodoError(null);
    } catch (err) {
      console.error('Failed to fetch todos:', err);
      setTodoError('TODOリストの取得に失敗しました。');
    } finally {
      setTodoLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshTodos();
  }, [refreshTodos]);

  const handleLoadSession = useCallback(
    async (sessionId: string) => {
      setCurrentSessionLoading(true);
      try {
        const session = await loadChatSession(sessionId);
        applySessionDetail(session);
        setSessionError(null);
        await refreshSessions(sessionSearch);
      } catch (err) {
        console.error('Failed to load session:', err);
        const message =
          err instanceof Error ? err.message : 'セッションの読み込みに失敗しました。';
        setSessionError(message);
      } finally {
        setCurrentSessionLoading(false);
      }
    },
    [applySessionDetail, refreshSessions, sessionSearch],
  );

  const handleResetSession = useCallback(async () => {
    setCurrentSessionLoading(true);
    try {
      const session = await resetChatSession();
      applySessionDetail(session);
      setSessionError(null);
      await refreshSessions(sessionSearch);
    } catch (err) {
      console.error('Failed to reset session:', err);
      const message =
        err instanceof Error ? err.message : '新しいセッションの作成に失敗しました。';
      setSessionError(message);
    } finally {
      setCurrentSessionLoading(false);
    }
  }, [applySessionDetail, refreshSessions, sessionSearch]);

  const handleSessionSearch = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      void refreshSessions(sessionSearch);
    },
    [refreshSessions, sessionSearch],
  );

  const handleRefreshSessionsClick = useCallback(() => {
    void refreshSessions(sessionSearch);
  }, [refreshSessions, sessionSearch]);

  const handleCurrentSessionRefresh = useCallback(() => {
    void loadCurrentSession();
  }, [loadCurrentSession]);

  // 能動会話が有効な場合、定期的に保留メッセージをポーリング
  useEffect(() => {
    if (!proactiveChatEnabled) return;

    const interval = setInterval(async () => {
      try {
        const pendingMessages = await getPendingProactiveMessages();
        if (pendingMessages.length > 0) {
          const newMessages: MessageEntry[] = pendingMessages.map(msg => ({
            id: createId(),
            role: 'assistant' as Role,
            content: msg.text,
            details: msg.details || undefined,
            timestamp: msg.timestamp * 1000, // 秒からミリ秒に変換
          }));
          setMessages(prev => [...prev, ...newMessages]);
        }
      } catch (err) {
        console.error('Failed to fetch pending messages:', err);
      }
    }, 10000); // 10秒ごと

    return () => clearInterval(interval);
  }, [proactiveChatEnabled]);

  async function handleToggleProactiveChat(enabled: boolean): Promise<void> {
    try {
      await toggleProactiveChat(enabled);
      setProactiveChatEnabled(enabled);
      localStorage.setItem('proactiveChatEnabled', enabled.toString());
    } catch (err) {
      const message = err instanceof Error ? err.message : '能動会話の切り替えに失敗しました';
      setError(message);
      console.error('Failed to toggle proactive chat:', err);
    }
  }

  async function handleSubmit(evt: FormEvent<HTMLFormElement>): Promise<void> {
    evt.preventDefault();
    if (!input.trim() || submitting) {
      return;
    }

    const messageId = createId();
    const userEntry: MessageEntry = {
      id: messageId,
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userEntry]);
    setInput('');
    setError(null);
    setSubmitting(true);

    try {
      const response = await postChatMessage(
        userEntry.content,
        playAudio,
        selectedModel || undefined,
      );
      const assistantEntry: MessageEntry = {
        id: createId(),
        role: 'assistant',
        content: response.voice_plan?.text ?? '応答が取得できませんでした。',
        details: response,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, assistantEntry]);
      await loadCurrentSession();
      await refreshSessions(sessionSearch);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '未知のエラーが発生しました。';
      setError(message);
      setMessages(prev =>
        prev.map(entry =>
          entry.id === messageId
            ? {
                ...entry,
                details: {
                  played_audio: false,
                },
              }
            : entry,
        ),
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleTodoSubmit(evt: FormEvent<HTMLFormElement>): Promise<void> {
    evt.preventDefault();
    if (!todoForm.title.trim()) {
      setTodoError('タイトルを入力してください');
      return;
    }

    try {
      await createTodo({
        title: todoForm.title.trim(),
        description: todoForm.description.trim(),
        due_date: todoForm.dueDate ? todoForm.dueDate : null,
        status: todoForm.status,
      });
      setTodoForm({
        title: '',
        description: '',
        dueDate: '',
        status: 'pending',
      });
      setTodoError(null);
      await refreshTodos();
    } catch (err) {
      console.error('Failed to create todo:', err);
      const message = err instanceof Error ? err.message : 'TODOの作成に失敗しました。';
      setTodoError(message);
    }
  }

  async function updateTodoWithState(
    todoId: number,
    updater: () => Promise<unknown>,
  ): Promise<void> {
    setUpdatingTodoIds(prev => {
      const next = new Set(prev);
      next.add(todoId);
      return next;
    });
    try {
      await updater();
      await refreshTodos();
    } catch (err) {
      console.error('Failed to update todo:', err);
      const message = err instanceof Error ? err.message : 'TODOの更新に失敗しました。';
      setTodoError(message);
    } finally {
      setUpdatingTodoIds(prev => {
        const next = new Set(prev);
        next.delete(todoId);
        return next;
      });
    }
  }

  function isTodoUpdating(todoId: number): boolean {
    return updatingTodoIds.has(todoId);
  }

  async function handleTodoStatusChange(todoId: number, status: TodoStatus): Promise<void> {
    await updateTodoWithState(todoId, () => updateTodo(todoId, { status }));
  }

  async function handleTodoDueDateChange(todoId: number, value: string): Promise<void> {
    await updateTodoWithState(todoId, () => updateTodo(todoId, { due_date: value || null }));
  }

  async function handleTodoDelete(todoId: number): Promise<void> {
    await updateTodoWithState(todoId, () => deleteTodo(todoId));
  }

  const sortedTodos = useMemo(() => {
    return [...todos].sort((a, b) => {
      if (a.status === b.status) {
        return (a.due_date ?? '').localeCompare(b.due_date ?? '');
      }
      if (a.status === 'done') return 1;
      if (b.status === 'done') return -1;
      return a.status.localeCompare(b.status);
    });
  }, [todos]);

  return (
    <div className="app">
      <header className="app__header">
        <h1>AI Secretary</h1>
        <div className="app__controls">
          <label className="app__checkbox">
            <input
              type="checkbox"
              checked={playAudio}
              onChange={event => setPlayAudio(event.target.checked)}
            />
            サーバーで音声再生
          </label>
          <label className="app__checkbox">
            <input
              type="checkbox"
              checked={proactiveChatEnabled}
              onChange={event => handleToggleProactiveChat(event.target.checked)}
            />
            AI側から定期的に話しかける
          </label>
          <label className="app__model-select">
            <span>モデル:</span>
            <select
              value={selectedModel}
              onChange={event => setSelectedModel(event.target.value)}
              disabled={submitting}
            >
              {availableModels.map(model => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <main className="app__main">
        <div className="app__layout">
        <SessionSidebar
          sessions={sessionSummaries}
          searchValue={sessionSearch}
          error={sessionError}
          sessionsLoading={sessionsLoading}
          currentSessionId={currentSessionId}
          currentSessionLoading={currentSessionLoading}
          onSearchChange={setSessionSearch}
          onSearchSubmit={handleSessionSearch}
          onRefresh={handleRefreshSessionsClick}
          onSelectSession={handleLoadSession}
          onCreateNew={handleResetSession}
          onSyncCurrent={handleCurrentSessionRefresh}
        />
          <div className="app__content">
            <section className="chat">
              <div className="chat__session-info">
                <div>
                  <p className="chat__session-label">選択中のセッション</p>
                  <h2>{currentSessionTitle}</h2>
                </div>
                <div className="chat__session-meta">
                  <span>ID: {currentSessionId ?? '未割り当て'}</span>
                  {currentSessionLoading && (
                    <span className="chat__session-status">同期中...</span>
                  )}
                </div>
              </div>
              {sortedMessages.length === 0 ? (
                <p className="chat__placeholder">最初のメッセージを入力してください。</p>
              ) : (
                <ul className="chat__messages">
                  {sortedMessages.map(entry => (
                    <li key={entry.id} className={`chat__message chat__message--${entry.role}`}>
                      <div className="chat__meta">
                        <span className="chat__role">
                          {entry.role === 'user' ? 'あなた' : 'AI秘書'}
                        </span>
                        <span className="chat__timestamp">{formatTimestamp(entry.timestamp)}</span>
                      </div>
                      <p className="chat__content">{entry.content}</p>
                      {entry.role === 'assistant' && entry.details && (
                        <details className="chat__details">
                          <summary>詳細</summary>
                          <div>
                            <p>音声ファイル: {entry.details.audio_path ?? 'なし'}</p>
                            <p>音声再生: {entry.details.played_audio ? '再生済み' : '未再生'}</p>
                            {entry.details.voice_plan && (
                              <pre className="chat__json">
                                {JSON.stringify(entry.details.voice_plan, null, 2)}
                              </pre>
                            )}
                          </div>
                        </details>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <TodoPanel
              todos={sortedTodos}
              todoForm={todoForm}
              todoLoading={todoLoading}
              todoError={todoError}
              statusLabels={statusLabels}
              statusOptions={statusOptions}
              isTodoUpdating={isTodoUpdating}
              onFormChange={handleTodoFormChange}
              onSubmit={handleTodoSubmit}
              onRefresh={() => void refreshTodos()}
              onStatusChange={handleTodoStatusChange}
              onDueDateChange={handleTodoDueDateChange}
              onDelete={handleTodoDelete}
            />
      </div>
    </div>
      </main>

      <footer className="app__footer">
        <form className="chat-input" onSubmit={handleSubmit}>
          <textarea
            className="chat-input__textarea"
            placeholder="メッセージを入力... (Ctrl+Enterで送信)"
            value={input}
            onChange={event => setInput(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && event.ctrlKey) {
                event.preventDefault();
                handleSubmit(event as unknown as FormEvent<HTMLFormElement>);
              }
            }}
            disabled={submitting}
            rows={3}
          />
          <button className="chat-input__submit" type="submit" disabled={submitting}>
            {submitting ? '送信中...' : '送信'}
          </button>
        </form>
        {error && <p className="chat-input__error">エラー: {error}</p>}
      </footer>
    </div>
  );
}
