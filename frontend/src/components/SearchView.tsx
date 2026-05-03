import { FormEvent } from 'react';

import { navigateToDocumentChunks, navigateToWorkspace } from '../router';
import { Course, SearchResult } from '../types';

type SearchViewProps = {
  course: Course | null;
  query: string;
  retrievalMode: string;
  results: SearchResult[];
  loading: boolean;
  onQueryChange: (value: string) => void;
  onRetrievalModeChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
};

export function SearchView({
  course,
  query,
  retrievalMode,
  results,
  loading,
  onQueryChange,
  onRetrievalModeChange,
  onSubmit,
}: SearchViewProps) {
  return (
    <section className="chunk-page">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Course Search</p>
            <h2>{course ? course.name : 'Search materials'}</h2>
            <p className="section-copy">
              Search child chunks inside one course with keyword, vector, or hybrid retrieval.
            </p>
          </div>
          <button type="button" className="link-button" onClick={navigateToWorkspace}>Back to workspace</button>
        </div>
        <form className="search-form" onSubmit={onSubmit}>
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search a topic, term, or concept"
          />
          <select value={retrievalMode} onChange={(event) => onRetrievalModeChange(event.target.value)}>
            <option value="keyword">Keyword</option>
            <option value="vector">Vector</option>
            <option value="hybrid">Hybrid</option>
          </select>
          <button type="submit" disabled={loading || !query.trim()}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Results</h2>
        </div>
        {results.length === 0 ? (
          <p className="empty-state">No results yet. Run a query to search the indexed child chunks.</p>
        ) : (
          <div className="chunk-list">
            {results.map((result) => (
              <article className="chunk-card" key={result.chunk_id}>
                <p className="chunk-meta">
                  {result.filename}
                  {result.page_number ? ` · page ${result.page_number}` : ''}
                  {result.section_title ? ` · ${result.section_title}` : ''}
                  {` · score ${result.score.toFixed(3)}`}
                </p>
                <pre>{result.text}</pre>
                <div className="result-actions">
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => course && navigateToDocumentChunks(course.id, result.document_id)}
                  >
                    Open source chunks
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
