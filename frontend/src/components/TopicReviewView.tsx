import { FormEvent } from 'react';

import { navigateToDocumentChunks, navigateToTopics, navigateToTopicReview } from '../router';
import { ChatMessage, Course, TopicReview } from '../types';

type TopicReviewViewProps = {
  course: Course | null;
  review: TopicReview | null;
  loading: boolean;
  chatQuery: string;
  chatLoading: boolean;
  chatMessages: ChatMessage[];
  onChatQueryChange: (value: string) => void;
  onChatSubmit: (event: FormEvent) => void;
  onMasteryChange: (status: 'not_started' | 'reviewing' | 'mastered') => void;
};

function stripTopicPromptPrefix(content: string) {
  return content.replace(/^About the topic ".*?":\s*/i, '');
}

export function TopicReviewView({
  course,
  review,
  loading,
  chatQuery,
  chatLoading,
  chatMessages,
  onChatQueryChange,
  onChatSubmit,
  onMasteryChange,
}: TopicReviewViewProps) {
  const topic = review?.topic ?? null;
  const turns = [];
  for (let index = 0; index < chatMessages.length; index += 1) {
    const message = chatMessages[index];
    if (message.role !== 'user') continue;
    const assistant = chatMessages[index + 1]?.role === 'assistant' ? chatMessages[index + 1] : null;
    turns.push({ user: message, assistant });
  }

  return (
    <section className="chunk-page">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Topic Review</p>
            <h2>{topic?.name || 'Topic review'}</h2>
            <p className="section-copy">
              {course ? `${course.name}${course.term ? ` · ${course.term}` : ''}` : 'Selected course topic'}
            </p>
          </div>
          <div className="result-actions">
            {course && (
              <button type="button" className="link-button" onClick={() => navigateToTopics(course.id)}>
                Back to topics
              </button>
            )}
          </div>
        </div>
      </section>

      {loading ? (
        <section className="panel">
          <p className="empty-state">Loading topic review...</p>
        </section>
      ) : !review || !topic ? (
        <section className="panel">
          <p className="empty-state">Topic review is not available for this topic.</p>
        </section>
      ) : (
        <>
          <section className="panel">
            <div className="section-heading">
              <h2>Overview</h2>
              <p className="document-meta">
                importance {topic.importance} · difficulty {topic.difficulty} · {review.source_chunks.length} supporting chunks · {topic.mastery_status.replace('_', ' ')}
              </p>
            </div>
            {topic.description && <p className="section-copy">{topic.description}</p>}
            {topic.keywords.length > 0 && (
              <div className="tag-list">
                {topic.keywords.map((keyword) => (
                  <span className="tag-chip" key={keyword}>
                    {keyword}
                  </span>
                ))}
              </div>
            )}
            <div className="result-actions">
              {topic.mastery_status !== 'reviewing' && (
                <button type="button" className="link-button" onClick={() => onMasteryChange('reviewing')}>
                  Mark reviewing
                </button>
              )}
              {topic.mastery_status !== 'mastered' && (
                <button type="button" onClick={() => onMasteryChange('mastered')}>
                  Mark mastered
                </button>
              )}
              {topic.mastery_status !== 'not_started' && (
                <button type="button" className="link-button" onClick={() => onMasteryChange('not_started')}>
                  Reset status
                </button>
              )}
            </div>
            {topic.last_reviewed_at && (
              <p className="document-meta">Last reviewed {new Date(topic.last_reviewed_at).toLocaleString()}</p>
            )}
          </section>

          <section className="panel">
            <div className="section-heading">
              <h2>Source Chunks</h2>
              <p className="section-copy">These are the chunks currently supporting this topic.</p>
            </div>
            <div className="chunk-list">
              {review.source_chunks.map((chunk) => (
                <article className="chunk-card" key={chunk.chunk_id}>
                  <p className="chunk-meta">
                    {chunk.filename}
                    {chunk.page_number ? ` · page ${chunk.page_number}` : ''}
                    {chunk.section_title ? ` · ${chunk.section_title}` : ''}
                  </p>
                  <pre>{chunk.text}</pre>
                  <div className="result-actions">
                    {course && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => navigateToDocumentChunks(course.id, chunk.document_id)}
                      >
                        Open full document chunks
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Ask This Topic</h2>
                <p className="section-copy">Ask follow-up questions while staying anchored to this topic and the course materials.</p>
              </div>
            </div>
            <form className="form-stack" onSubmit={onChatSubmit}>
              <div className="topic-chat-form">
                <input
                  value={chatQuery}
                  onChange={(event) => onChatQueryChange(event.target.value)}
                  placeholder={topic ? `Ask about ${topic.name}` : 'Ask about this topic'}
                />
                <button type="submit" disabled={chatLoading || !chatQuery.trim()}>
                  {chatLoading ? 'Thinking...' : 'Ask'}
                </button>
              </div>
            </form>
            {turns.length === 0 ? (
              <p className="empty-state">Ask a question to start a topic-focused review conversation.</p>
            ) : (
              <div className="chat-thread">
                {[...turns].reverse().map((turn) => (
                  <article className="chat-turn" key={turn.user.id}>
                    <section className="chat-message chat-user">
                      <p className="chunk-meta">Question</p>
                      <p>{stripTopicPromptPrefix(turn.user.content)}</p>
                    </section>
                    {turn.assistant && (
                      <section className="chat-message chat-assistant">
                        <p className="chunk-meta">Answer</p>
                        <p>{turn.assistant.content}</p>
                        {turn.assistant.sources.length > 0 && (
                          <div className="source-list">
                            {turn.assistant.sources.map((source, index) => (
                              <div className="source-card" key={`${turn.user.id}-${source.chunk_id}-${index}`}>
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

          <section className="panel">
            <div className="section-heading">
              <h2>Related Topics</h2>
            </div>
            {review.related_topics.length === 0 ? (
              <p className="empty-state">No closely related topics yet.</p>
            ) : (
              <div className="topic-list">
                {review.related_topics.map((relatedTopic) => (
                  <article className="topic-card" key={relatedTopic.id}>
                    <div className="section-heading topic-heading">
                      <div>
                        <h3>{relatedTopic.name}</h3>
                        <p className="document-meta">
                          importance {relatedTopic.importance} · difficulty {relatedTopic.difficulty}
                        </p>
                      </div>
                      {course && (
                        <button type="button" className="link-button" onClick={() => navigateToTopicReview(course.id, relatedTopic.id)}>
                          Review
                        </button>
                      )}
                    </div>
                    {relatedTopic.description && <p className="section-copy">{relatedTopic.description}</p>}
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
