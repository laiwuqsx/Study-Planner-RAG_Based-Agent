import { FormEvent } from 'react';

import { navigateToTopicReview, navigateToWorkspace } from '../router';
import { Course, StudyPlan, StudyPlanGenerateInput } from '../types';

type StudyPlanViewProps = {
  course: Course | null;
  plan: StudyPlan | null;
  loading: boolean;
  form: StudyPlanGenerateInput;
  onFormChange: (next: StudyPlanGenerateInput) => void;
  onGenerate: (event: FormEvent) => void;
  onRegenerate: () => void;
  onItemStatusChange: (itemId: number, status: 'pending' | 'in_progress' | 'completed') => void;
};

export function StudyPlanView({ course, plan, loading, form, onFormChange, onGenerate, onRegenerate, onItemStatusChange }: StudyPlanViewProps) {
  return (
    <section className="chunk-page">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Study Plan</p>
            <h2>{course ? course.name : 'Study plan'}</h2>
            <p className="section-copy">
              Generate a topic-level plan from the current course topics and a small amount of representative context.
            </p>
          </div>
          <button type="button" className="link-button" onClick={navigateToWorkspace}>
            Back to workspace
          </button>
        </div>

        <form className="plan-form" onSubmit={onGenerate}>
          <label className="plan-form-wide">
            Goal
            <textarea
              rows={3}
              value={form.goal}
              onChange={(event) => onFormChange({ ...form, goal: event.target.value })}
              placeholder="Prepare a focused review plan for the next two weeks."
            />
          </label>
          <label>
            Sessions / week
            <input
              type="number"
              min={1}
              max={14}
              value={form.sessions_per_week}
              onChange={(event) => onFormChange({ ...form, sessions_per_week: Number(event.target.value) || 1 })}
            />
          </label>
          <label>
            Minutes / session
            <input
              type="number"
              min={20}
              max={240}
              value={form.minutes_per_session}
              onChange={(event) => onFormChange({ ...form, minutes_per_session: Number(event.target.value) || 20 })}
            />
          </label>
          <label>
            Topic limit
            <input
              type="number"
              min={1}
              max={16}
              value={form.topic_limit}
              onChange={(event) => onFormChange({ ...form, topic_limit: Number(event.target.value) || 1 })}
            />
          </label>
          <div className="result-actions plan-actions">
            <button type="submit" disabled={loading}>
              {loading ? 'Generating...' : plan ? 'Generate new plan' : 'Generate plan'}
            </button>
            {plan && (
              <button type="button" className="link-button" onClick={onRegenerate} disabled={loading}>
                {loading ? 'Working...' : 'Regenerate'}
              </button>
            )}
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>{plan ? plan.title : 'Current plan'}</h2>
            {plan && (
              <p className="document-meta">
                {plan.generation_mode} plan · {plan.completed_item_count}/{plan.item_count} completed
              </p>
            )}
          </div>
        </div>

        {!plan ? (
          <p className="empty-state">No study plan yet. Generate one from the current course topics.</p>
        ) : (
          <div className="plan-layout">
            <section className="plan-summary-card">
              <p className="section-copy">{plan.summary}</p>
            </section>

            <div className="plan-item-list">
              {plan.items.map((item) => (
                <article className="plan-item-card" key={item.id}>
                  <div className="section-heading topic-heading">
                    <div>
                      <p className="plan-order">Step {item.order_index}</p>
                      <h3>{item.title}</h3>
                      <p className="document-meta">
                        {item.estimated_effort_minutes} min · importance {item.importance} · difficulty {item.difficulty} · {item.status.replace('_', ' ')}
                      </p>
                    </div>
                  </div>
                  {item.notes && <p className="section-copy">{item.notes}</p>}
                  {item.focus_points.length > 0 && (
                    <div className="tag-list">
                      {item.focus_points.map((point) => (
                        <span className="tag-chip" key={point}>
                          {point}
                        </span>
                      ))}
                    </div>
                  )}
                  {item.context_snippets.length > 0 && (
                    <div className="plan-snippets">
                      {item.context_snippets.map((snippet, index) => (
                        <p className="plan-snippet" key={`${item.id}-${index}`}>
                          {snippet}
                        </p>
                      ))}
                    </div>
                  )}
                  {course && (
                    <div className="result-actions">
                      {item.status !== 'in_progress' && (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => onItemStatusChange(item.id, 'in_progress')}
                        >
                          Start
                        </button>
                      )}
                      {item.status !== 'completed' && (
                        <button
                          type="button"
                          onClick={() => onItemStatusChange(item.id, 'completed')}
                        >
                          Complete
                        </button>
                      )}
                      {item.status !== 'pending' && (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => onItemStatusChange(item.id, 'pending')}
                        >
                          Reset
                        </button>
                      )}
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => navigateToTopicReview(course.id, item.topic_id)}
                      >
                        Review topic
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>
        )}
      </section>
    </section>
  );
}
