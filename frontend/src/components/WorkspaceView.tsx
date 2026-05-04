import { FormEvent } from 'react';

import { MATERIAL_TYPE_OPTIONS } from '../constants';
import { navigateToChat, navigateToDocumentChunks, navigateToSearch, navigateToTopics } from '../router';
import { Course, CourseForm, DocumentRecord, ProcessingJob } from '../types';
import { formatDate } from '../utils';

type WorkspaceViewProps = {
  courses: Course[];
  selectedCourseId: number | null;
  courseForm: CourseForm;
  editingId: number | null;
  documents: DocumentRecord[];
  selectedFile: File | null;
  materialType: string;
  activeJob: ProcessingJob | null;
  loading: boolean;
  onCourseSubmit: (event: FormEvent) => void;
  onCourseFormChange: (next: CourseForm) => void;
  onCancelEdit: () => void;
  onRefreshCourses: () => void;
  onSelectCourse: (courseId: number) => void;
  onStartEdit: (course: Course) => void;
  onDeleteCourse: (courseId: number) => void;
  onUploadSubmit: (event: FormEvent) => void;
  onMaterialTypeChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
  onRefreshDocuments: () => void;
  onDeleteDocument: (document: DocumentRecord) => void;
};

export function WorkspaceView({
  courses,
  selectedCourseId,
  courseForm,
  editingId,
  documents,
  selectedFile,
  materialType,
  activeJob,
  loading,
  onCourseSubmit,
  onCourseFormChange,
  onCancelEdit,
  onRefreshCourses,
  onSelectCourse,
  onStartEdit,
  onDeleteCourse,
  onUploadSubmit,
  onMaterialTypeChange,
  onFileChange,
  onRefreshDocuments,
  onDeleteDocument,
}: WorkspaceViewProps) {
  const selectedCourse = courses.find((course) => course.id === selectedCourseId) || null;

  return (
    <section className="workspace-grid">
      <aside className="stack-column">
        <form className="panel form-stack" onSubmit={onCourseSubmit}>
          <div className="section-heading">
            <h2>{editingId ? 'Edit course' : 'Create course'}</h2>
            {editingId && (
              <button type="button" className="link-button" onClick={onCancelEdit}>
                Cancel
              </button>
            )}
          </div>
          <label>
            Course name
            <input
              value={courseForm.name}
              onChange={(event) => onCourseFormChange({ ...courseForm, name: event.target.value })}
              placeholder="CS 412"
              required
            />
          </label>
          <label>
            Term
            <input
              value={courseForm.term}
              onChange={(event) => onCourseFormChange({ ...courseForm, term: event.target.value })}
              placeholder="Spring 2026"
            />
          </label>
          <label>
            Description
            <textarea
              value={courseForm.description}
              onChange={(event) => onCourseFormChange({ ...courseForm, description: event.target.value })}
              placeholder="What this course covers"
              rows={4}
            />
          </label>
          <button type="submit" disabled={loading}>
            {editingId ? 'Save changes' : 'Create course'}
          </button>
        </form>

        <section className="panel">
          <div className="section-heading">
            <h2>Your courses</h2>
            <button type="button" onClick={onRefreshCourses}>Refresh</button>
          </div>
          {courses.length === 0 ? (
            <p className="empty-state">No courses yet. Create one to start organizing study materials.</p>
          ) : (
            <div className="course-list">
              {courses.map((course) => (
                <article className={`course-card ${selectedCourseId === course.id ? 'is-selected' : ''}`} key={course.id}>
                  <button type="button" className="course-select" onClick={() => onSelectCourse(course.id)}>
                    <div>
                      <h3>{course.name}</h3>
                      {course.term && <p className="course-term">{course.term}</p>}
                      {course.description && <p>{course.description}</p>}
                    </div>
                  </button>
                  <div className="card-actions">
                    <button type="button" onClick={() => onStartEdit(course)}>Edit</button>
                    <button type="button" className="danger" onClick={() => onDeleteCourse(course.id)}>Delete</button>
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
              <h2>{selectedCourse ? selectedCourse.name : 'Course materials'}</h2>
              <p className="section-copy">
                {selectedCourse
                  ? 'Upload PDF or DOCX files and track processing progress.'
                  : 'Select a course to start uploading materials.'}
              </p>
            </div>
            {selectedCourse && (
              <div className="result-actions">
                <button type="button" className="link-button" onClick={() => navigateToChat(selectedCourse.id)}>
                  Ask course
                </button>
                <button type="button" className="link-button" onClick={() => navigateToTopics(selectedCourse.id)}>
                  View topics
                </button>
                <button type="button" className="link-button" onClick={() => navigateToSearch(selectedCourse.id)}>
                  Search chunks
                </button>
              </div>
            )}
          </div>

          <form className="form-stack" onSubmit={onUploadSubmit}>
            <label>
              Material type
              <select value={materialType} onChange={(event) => onMaterialTypeChange(event.target.value)} disabled={!selectedCourse}>
                {MATERIAL_TYPE_OPTIONS.map((option) => (
                  <option value={option} key={option}>
                    {option.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </label>
            <label>
              File
              <input
                id="course-upload-input"
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) => onFileChange(event.target.files?.[0] || null)}
                disabled={!selectedCourse}
              />
            </label>
            <button type="submit" disabled={loading || !selectedCourse || !selectedFile}>
              {loading ? 'Working...' : 'Upload material'}
            </button>
          </form>
        </section>

        {activeJob && (
          <section className="panel">
            <div className="section-heading">
              <h2>Processing job #{activeJob.id}</h2>
              <span className={`status-badge status-${activeJob.status}`}>{activeJob.status}</span>
            </div>
            <p className="section-copy">{activeJob.error || activeJob.message}</p>
            <div className="step-list">
              {activeJob.steps.map((step) => (
                <div className={`step-row step-${step.status}`} key={step.step}>
                  <strong>{step.step}</strong>
                  <span>{step.status.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="panel">
          <div className="section-heading">
            <h2>Uploaded materials</h2>
            {selectedCourse && <button type="button" onClick={onRefreshDocuments}>Refresh</button>}
          </div>
          {!selectedCourse ? (
            <p className="empty-state">Select a course to view its materials.</p>
          ) : documents.length === 0 ? (
            <p className="empty-state">No materials uploaded for this course yet.</p>
          ) : (
            <div className="document-list">
              {documents.map((document) => (
                <article className="document-card" key={document.id}>
                  <div>
                    <h3>{document.filename}</h3>
                    <p className="document-meta">
                      {document.material_type.replaceAll('_', ' ')} · {document.file_type.toUpperCase()}
                    </p>
                    {document.chunk_count > 0 && <p className="document-meta">{document.chunk_count} child chunks</p>}
                    <p className="document-meta">Updated {formatDate(document.updated_at)}</p>
                  </div>
                  <div className="document-actions">
                    <span className={`status-badge status-${document.status}`}>{document.status}</span>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => selectedCourse && navigateToDocumentChunks(selectedCourse.id, document.id)}
                    >
                      View chunks
                    </button>
                    <button type="button" className="danger" onClick={() => onDeleteDocument(document)}>Delete</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </section>
  );
}
