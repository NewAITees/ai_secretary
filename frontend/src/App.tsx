import { FormEvent, useEffect, useMemo, useState } from 'react';

import {
  ChatResponsePayload,
  getAvailableModels,
  getPendingProactiveMessages,
  getProactiveChatStatus,
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

export default function App(): JSX.Element {
  const [messages, setMessages] = useState<MessageEntry[]>([]);
  const [input, setInput] = useState('');
  const [playAudio, setPlayAudio] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [proactiveChatEnabled, setProactiveChatEnabled] = useState(false);

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
