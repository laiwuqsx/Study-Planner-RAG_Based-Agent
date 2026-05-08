import { ChildChunk, Course, DocumentChunkSummary, DocumentRecord, ParentChunk } from '../types';

type DocumentChunksViewProps = {
  course: Course | null;
  document: DocumentRecord | null;
  chunkSummary: DocumentChunkSummary | null;
  loading: boolean;
  onBack: () => void;
};

function ChunkCard({
  kind,
  index,
  pageNumber,
  sectionTitle,
  text,
}: {
  kind: 'Parent' | 'Child';
  index: number;
  pageNumber: number | null;
  sectionTitle: string;
  text: string;
}) {
  return (
    <article className="chunk-card">
      <p className="chunk-meta">
        {kind} #{index}
        {pageNumber ? ` · page ${pageNumber}` : ''}
        {sectionTitle ? ` · ${sectionTitle}` : ''}
      </p>
      <pre>{text}</pre>
    </article>
  );
}

export function DocumentChunksView({
  course,
  document,
  chunkSummary,
  loading,
  onBack,
}: DocumentChunksViewProps) {
  return (
    <section className="chunk-page">
      <section className="panel">
        <div className="page-header">
          <div>
            <p className="eyebrow">Chunk Inspector</p>
            <h2>{document?.filename || 'Document chunks'}</h2>
            <p className="section-copy">
              {course ? `${course.name}${course.term ? ` · ${course.term}` : ''}` : 'Selected course material'}
            </p>
          </div>
          <button type="button" className="secondary-button" onClick={onBack}>Back to materials</button>
        </div>
      </section>

      <section className="panel">
        {loading ? (
          <p className="empty-state">Loading chunk details...</p>
        ) : !chunkSummary ? (
          <p className="empty-state">Chunk details are not available for this material.</p>
        ) : (
          <div className="chunk-layout">
            <div className="subsection-card">
              <div className="page-header compact">
                <div>
                  <p className="eyebrow">Hierarchy</p>
                  <h3>Parent chunks</h3>
                </div>
              </div>
              <div className="chunk-list">
                {chunkSummary.parent_chunks.map((chunk: ParentChunk) => (
                  <ChunkCard
                    key={chunk.id}
                    kind="Parent"
                    index={chunk.chunk_index}
                    pageNumber={chunk.page_number}
                    sectionTitle={chunk.section_title}
                    text={chunk.text}
                  />
                ))}
              </div>
            </div>
            <div className="subsection-card">
              <div className="page-header compact">
                <div>
                  <p className="eyebrow">Retrieval Units</p>
                  <h3>Child chunks</h3>
                </div>
              </div>
              <div className="chunk-list">
                {chunkSummary.child_chunks.map((chunk: ChildChunk) => (
                  <ChunkCard
                    key={chunk.id}
                    kind="Child"
                    index={chunk.chunk_index}
                    pageNumber={chunk.page_number}
                    sectionTitle={chunk.section_title}
                    text={chunk.text}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </section>
    </section>
  );
}
