import { FormEvent, useMemo, useState } from 'react';

import { ChatResponsePayload, postChatMessage } from './api';

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

  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => a.timestamp - b.timestamp),
    [messages],
  );

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
      const response = await postChatMessage(userEntry.content, playAudio);
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
            placeholder="メッセージを入力..."
            value={input}
            onChange={event => setInput(event.target.value)}
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
