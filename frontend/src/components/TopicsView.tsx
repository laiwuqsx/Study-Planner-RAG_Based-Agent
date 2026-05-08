import { navigateToTopicReview, navigateToWorkspace } from '../router';
import { Course, Topic } from '../types';

type TopicsViewProps = {
  course: Course | null;
  topics: Topic[];
  loading: boolean;
  onRefresh: () => void;
};

export function TopicsView({ course, topics, loading, onRefresh }: TopicsViewProps) {
  return (
    <section className="chunk-page">
      <section className="panel">
        <div className="page-header">
          <div>
            <p className="eyebrow">Course Topics</p>
            <h2>{course ? course.name : 'Topics'}</h2>
            <p className="section-copy">Extracted topics are grouped from indexed material chunks and organized for quick review.</p>
          </div>
          <div className="toolbar-actions">
            <button type="button" onClick={onRefresh} disabled={loading}>
              {loading ? 'Refreshing...' : 'Refresh topics'}
            </button>
            <button type="button" className="secondary-button" onClick={navigateToWorkspace}>
              Back to workspace
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="page-header compact">
          <div>
            <p className="eyebrow">Review Queue</p>
            <h2>Topic list</h2>
          </div>
        </div>
        {topics.length === 0 ? (
          <p className="empty-state">No topics yet. Upload materials or refresh extraction for this course.</p>
        ) : (
          <div className="topic-list">
            {topics.map((topic) => (
              <article className="topic-card" key={topic.id}>
                <div className="card-topline">
                  <span className={`status-badge status-${topic.mastery_status}`}>{topic.mastery_status.replace('_', ' ')}</span>
                  <span className="meta-pill">{topic.source_chunk_ids.length} source chunks</span>
                </div>
                <div className="section-heading topic-heading">
                  <div className="topic-card-body">
                    <h3>{topic.name}</h3>
                    <p className="document-meta">
                      importance {topic.importance} · difficulty {topic.difficulty}
                    </p>
                  </div>
                  {course && (
                    <button type="button" className="secondary-button" onClick={() => navigateToTopicReview(course.id, topic.id)}>
                      Review topic
                    </button>
                  )}
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
                {topic.prerequisites.length > 0 && (
                  <p className="document-meta">Prerequisites: {topic.prerequisites.join(', ')}</p>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
