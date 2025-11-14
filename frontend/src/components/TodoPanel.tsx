import type { FormEvent } from 'react';

import type { TodoItem, TodoStatus } from '../api';

interface TodoFormState {
  title: string;
  description: string;
  dueDate: string;
  status: TodoStatus;
}

interface TodoPanelProps {
  todos: TodoItem[];
  todoForm: TodoFormState;
  todoLoading: boolean;
  todoError: string | null;
  statusLabels: Record<TodoStatus, string>;
  statusOptions: TodoStatus[];
  isTodoUpdating: (todoId: number) => boolean;
  onFormChange: (updates: Partial<TodoFormState>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onRefresh: () => void;
  onStatusChange: (todoId: number, status: TodoStatus) => void;
  onDueDateChange: (todoId: number, value: string) => void;
  onDelete: (todoId: number) => void;
}

export function TodoPanel({
  todos,
  todoForm,
  todoLoading,
  todoError,
  statusLabels,
  statusOptions,
  isTodoUpdating,
  onFormChange,
  onSubmit,
  onRefresh,
  onStatusChange,
  onDueDateChange,
  onDelete,
}: TodoPanelProps): JSX.Element {
  return (
    <section className="todos">
      <div className="todos__header">
        <h2>TODOリスト</h2>
        <button type="button" className="todos__refresh" onClick={onRefresh} disabled={todoLoading}>
          {todoLoading ? '更新中…' : '再読み込み'}
        </button>
      </div>
      <form className="todo-form" onSubmit={onSubmit}>
        <div className="todo-form__row">
          <label>
            タイトル
            <input
              type="text"
              value={todoForm.title}
              onChange={event => onFormChange({ title: event.target.value })}
              required
            />
          </label>
          <label>
            期限
            <input
              type="date"
              value={todoForm.dueDate}
              onChange={event => onFormChange({ dueDate: event.target.value })}
            />
          </label>
          <label>
            状態
            <select
              value={todoForm.status}
              onChange={event => onFormChange({ status: event.target.value as TodoStatus })}
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
            onChange={event => onFormChange({ description: event.target.value })}
          />
        </label>
        <button type="submit" className="todo-form__submit">
          追加
        </button>
      </form>
      {todoError && <p className="todos__error">{todoError}</p>}
      <div className="todo-list">
        {todos.length === 0 ? (
          <p className="todos__placeholder">
            TODOは登録されていません。まずは上のフォームから追加してください。
          </p>
        ) : (
          todos.map(todo => (
            <article key={todo.id} className={`todo-card todo-card--${todo.status}`}>
              <div className="todo-card__header">
                <div>
                  <span className="todo-card__status">{statusLabels[todo.status]}</span>
                  <h3>{todo.title}</h3>
                </div>
                <button
                  type="button"
                  className="todo-card__delete"
                  onClick={() => onDelete(todo.id)}
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
                    onChange={event => onDueDateChange(todo.id, event.target.value)}
                    disabled={isTodoUpdating(todo.id)}
                  />
                </label>
                <label>
                  状態
                  <select
                    value={todo.status}
                    onChange={event => onStatusChange(todo.id, event.target.value as TodoStatus)}
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
                    onClick={() => onStatusChange(todo.id, 'done')}
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
  );
}
