import { FormEvent } from 'react';

import { navigateToWorkspace } from '../router';
import { ChatMessage, ChatSessionSummary, Course } from '../types';

type ChatViewProps = {
  course: Course | null;
  sessions: ChatSessionSummary[];
  activeSessionId: number | null;
  messages: ChatMessage[];
  query: string;
  retrievalMode: string;
  loading: boolean;
  onNewSession: () => void;
  onSelectSession: (sessionId: number) => void;
  onDeleteSession: (sessionId: number) => void;
  onQueryChange: (value: string) => void;
  onRetrievalModeChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
};

export function ChatView({
  course,
  sessions,
  activeSessionId,
  messages,
  query,
  retrievalMode,
  loading,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  onQueryChange,
  onRetrievalModeChange,
  onSubmit,
}: ChatViewProps) {
  const turns = [];
  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index];
    if (message.role !== 'user') continue;
    const assistant = messages[index + 1]?.role === 'assistant' ? messages[index + 1] : null;
    turns.push({ user: message, assistant });
  }

  return (
    <section className="workspace-grid">
      <aside className="stack-column">
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Course Chat</p>
              <h2>{course ? course.name : 'Chat'}</h2>
            </div>
            <button type="button" className="link-button" onClick={navigateToWorkspace}>
              Back
            </button>
          </div>
          <div className="result-actions">
            <button type="button" onClick={onNewSession}>New session</button>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <h2>Sessions</h2>
          </div>
          {sessions.length === 0 ? (
            <p className="empty-state">No saved sessions yet.</p>
          ) : (
            <div className="course-list">
              {sessions.map((session) => (
                <article className={`course-card ${activeSessionId === session.id ? 'is-selected' : ''}`} key={session.id}>
                  <button type="button" className="course-select" onClick={() => onSelectSession(session.id)}>
                    <h3>{session.title}</h3>
                  </button>
                  <div className="card-actions">
                    <button type="button" className="danger" onClick={() => onDeleteSession(session.id)}>Delete</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </aside>

      <section className="stack-column">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Ask course material</h2>
              <p className="section-copy">Latest question stays on top. Answers cite retrieved sources from this course only.</p>
            </div>
          </div>
          <form className="form-stack" onSubmit={onSubmit}>
            <div className="search-form">
              <input
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
                placeholder="Ask about course material"
              />
              <select value={retrievalMode} onChange={(event) => onRetrievalModeChange(event.target.value)}>
                <option value="keyword">Keyword</option>
                <option value="vector">Vector</option>
                <option value="hybrid">Hybrid</option>
              </select>
              <button type="submit" disabled={loading || !query.trim()}>
                {loading ? 'Thinking...' : 'Send'}
              </button>
            </div>
          </form>
        </section>

        <section className="panel">
          <div className="section-heading">
            <h2>Conversation</h2>
          </div>
          {turns.length === 0 ? (
            <p className="empty-state">Ask a question to retrieve relevant course chunks and generate a sourced answer.</p>
          ) : (
            <div className="chat-thread">
              {[...turns].reverse().map((turn) => (
                <article className="chat-turn" key={turn.user.id}>
                  <section className="chat-message chat-user">
                    <p className="chunk-meta">Question</p>
                    <p>{turn.user.content}</p>
                  </section>
                  {turn.assistant && (
                    <section className="chat-message chat-assistant">
                      <p className="chunk-meta">Answer</p>
                      <p>{turn.assistant.content}</p>
                      {turn.assistant.sources.length > 0 && (
                        <div className="source-list">
                          {turn.assistant.sources.map((source, index) => (
                            <div className="source-card" key={`${turn.assistant?.id}-${source.chunk_id}`}>
                              <p className="document-meta">
                                [{index + 1}] {source.filename}
                                {source.page_number ? ` · page ${source.page_number}` : ''}
                                {source.section_title ? ` · ${source.section_title}` : ''}
                              </p>
                              <pre>{source.text}</pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </section>
  );
}
