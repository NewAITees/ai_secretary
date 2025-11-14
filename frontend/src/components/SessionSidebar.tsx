import type { FormEvent } from 'react';

import type { ChatSessionSummary } from '../api';
import { formatSessionTimestamp } from '../utils/chat';

interface SessionSidebarProps {
  sessions: ChatSessionSummary[];
  searchValue: string;
  error: string | null;
  sessionsLoading: boolean;
  currentSessionId: string | null;
  currentSessionLoading: boolean;
  onSearchChange: (value: string) => void;
  onSearchSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRefresh: () => void;
  onSelectSession: (sessionId: string) => void;
  onCreateNew: () => void;
  onSyncCurrent: () => void;
}

export function SessionSidebar({
  sessions,
  searchValue,
  error,
  sessionsLoading,
  currentSessionId,
  currentSessionLoading,
  onSearchChange,
  onSearchSubmit,
  onRefresh,
  onSelectSession,
  onCreateNew,
  onSyncCurrent,
}: SessionSidebarProps): JSX.Element {
  return (
    <aside className="history">
      <div className="history__header">
        <h2>チャット履歴</h2>
        <button
          type="button"
          className="history__refresh"
          onClick={onRefresh}
          disabled={sessionsLoading}
        >
          {sessionsLoading ? '更新中…' : '最新表示'}
        </button>
      </div>
      <form className="history__search" onSubmit={onSearchSubmit}>
        <input
          type="text"
          placeholder="キーワード検索"
          value={searchValue}
          onChange={event => onSearchChange(event.target.value)}
        />
        <button type="submit">検索</button>
      </form>
      <div className="history__actions">
        <button type="button" onClick={onCreateNew} disabled={currentSessionLoading}>
          新規セッション
        </button>
        <button type="button" onClick={onSyncCurrent} disabled={currentSessionLoading}>
          現在の状態
        </button>
      </div>
      {error && <p className="history__error">{error}</p>}
      <div className="history__list-container">
        {sessionsLoading ? (
          <p className="history__placeholder">読み込み中...</p>
        ) : sessions.length === 0 ? (
          <p className="history__placeholder">保存済みの会話はありません。</p>
        ) : (
          <ul className="history__list">
            {sessions.map(session => {
              const isActive = session.session_id === currentSessionId;
              return (
                <li key={session.session_id}>
                  <button
                    type="button"
                    className={`history__item${isActive ? ' history__item--active' : ''}`}
                    onClick={() => onSelectSession(session.session_id)}
                    disabled={isActive && currentSessionLoading}
                  >
                    <span className="history__title">{session.title}</span>
                    <span className="history__meta">
                      更新: {formatSessionTimestamp(session.updated_at ?? session.created_at)}
                    </span>
                    <span className="history__meta">メッセージ: {session.message_count}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
