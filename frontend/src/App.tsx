import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import {
  ChatResponsePayload,
  TodoItem,
  TodoStatus,
  createTodo,
  getAvailableModels,
  getPendingProactiveMessages,
  getTodos,
  getProactiveChatStatus,
  updateTodo,
  deleteTodo,
  postChatMessage,
  toggleProactiveChat,
} from './api';

type Role = 'user' | 'assistant';

interface MessageEntry {
  id: string;
  role: Role;
  content: string;
  details?: ChatResponsePayload;
  timestamp: number;
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString();
}

function createId(): string {
  return crypto.randomUUID();
}

const statusLabels: Record<TodoStatus, string> = {
  pending: '未着手',
  in_progress: '進行中',
  done: '完了',
};

const statusOptions: TodoStatus[] = ['pending', 'in_progress', 'done'];

export default function App(): JSX.Element {
  const [messages, setMessages] = useState<MessageEntry[]>([]);
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

  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => a.timestamp - b.timestamp),
    [messages],
  );

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
    updater: () => Promise<void>,
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
        <section className="chat">
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
        <section className="todos">
          <div className="todos__header">
            <h2>TODOリスト</h2>
            <button
              type="button"
              className="todos__refresh"
              onClick={() => refreshTodos()}
              disabled={todoLoading}
            >
              {todoLoading ? '更新中…' : '再読み込み'}
            </button>
          </div>
          <form className="todo-form" onSubmit={handleTodoSubmit}>
            <div className="todo-form__row">
              <label>
                タイトル
                <input
                  type="text"
                  value={todoForm.title}
                  onChange={event =>
                    setTodoForm(prev => ({ ...prev, title: event.target.value }))
                  }
                  required
                />
              </label>
              <label>
                期限
                <input
                  type="date"
                  value={todoForm.dueDate}
                  onChange={event =>
                    setTodoForm(prev => ({ ...prev, dueDate: event.target.value }))
                  }
                />
              </label>
              <label>
                状態
                <select
                  value={todoForm.status}
                  onChange={event =>
                    setTodoForm(prev => ({
                      ...prev,
                      status: event.target.value as TodoStatus,
                    }))
                  }
                >
                  {statusOptions.map(status => (
                    <option key={status} value={status}>
                      {statusLabels[status]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="todo-form__description">
              詳細
              <textarea
                rows={2}
                value={todoForm.description}
                onChange={event =>
                  setTodoForm(prev => ({ ...prev, description: event.target.value }))
                }
              />
            </label>
            <button type="submit" className="todo-form__submit">
              追加
            </button>
          </form>
          {todoError && <p className="todos__error">{todoError}</p>}
          <div className="todo-list">
            {sortedTodos.length === 0 ? (
              <p className="todos__placeholder">
                TODOは登録されていません。まずは上のフォームから追加してください。
              </p>
            ) : (
              sortedTodos.map(todo => (
                <article key={todo.id} className={`todo-card todo-card--${todo.status}`}>
                  <div className="todo-card__header">
                    <div>
                      <span className="todo-card__status">{statusLabels[todo.status]}</span>
                      <h3>{todo.title}</h3>
                    </div>
                    <button
                      type="button"
                      className="todo-card__delete"
                      onClick={() => handleTodoDelete(todo.id)}
                      disabled={isTodoUpdating(todo.id)}
                    >
                      削除
                    </button>
                  </div>
                  <p className="todo-card__description">
                    {todo.description || '説明は設定されていません。'}
                  </p>
                  <div className="todo-card__controls">
                    <label>
                      期限
                      <input
                        type="date"
                        value={todo.due_date ?? ''}
                        onChange={event =>
                          handleTodoDueDateChange(todo.id, event.target.value)
                        }
                        disabled={isTodoUpdating(todo.id)}
                      />
                    </label>
                    <label>
                      状態
                      <select
                        value={todo.status}
                        onChange={event =>
                          handleTodoStatusChange(todo.id, event.target.value as TodoStatus)
                        }
                        disabled={isTodoUpdating(todo.id)}
                      >
                        {statusOptions.map(status => (
                          <option key={status} value={status}>
                            {statusLabels[status]}
                          </option>
                        ))}
                      </select>
                    </label>
                    {todo.status !== 'done' && (
                      <button
                        type="button"
                        className="todo-card__complete"
                        onClick={() => handleTodoStatusChange(todo.id, 'done')}
                        disabled={isTodoUpdating(todo.id)}
                      >
                        完了にする
                      </button>
                    )}
                  </div>
                  <footer className="todo-card__footer">
                    <small>ID: {todo.id}</small>
                    <small>更新: {new Date(todo.updated_at).toLocaleString()}</small>
                  </footer>
                </article>
              ))
            )}
          </div>
        </section>
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
