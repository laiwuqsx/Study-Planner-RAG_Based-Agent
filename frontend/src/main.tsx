import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type AuthMode = 'login' | 'register';

type User = {
  id: number;
  username: string;
  created_at: string;
};

type Course = {
  id: number;
  name: string;
  term: string;
  description: string;
  created_at: string;
  updated_at: string;
};

type CourseForm = {
  name: string;
  term: string;
  description: string;
};

type DocumentRecord = {
  id: number;
  course_id: number;
  filename: string;
  file_type: string;
  material_type: string;
  status: string;
  chunk_count: number;
  topic_count: number;
  created_at: string;
  updated_at: string;
};

type JobStep = {
  step: string;
  status: string;
  message: string;
};

type ProcessingJob = {
  id: number;
  user_id: number;
  course_id: number;
  document_id: number;
  status: string;
  current_step: string;
  message: string;
  error: string;
  steps: JobStep[];
  created_at: string;
  updated_at: string;
};

type UploadResponse = {
  document: DocumentRecord;
  job: ProcessingJob;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'studyPlannerToken';
const MATERIAL_TYPE_OPTIONS = ['lecture_slides', 'course_notes', 'assignment', 'example_problems', 'syllabus', 'other'];

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '');
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [courseForm, setCourseForm] = useState<CourseForm>({ name: '', term: '', description: '' });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [materialType, setMaterialType] = useState('other');
  const [activeJob, setActiveJob] = useState<ProcessingJob | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const isAuthenticated = useMemo(() => Boolean(token && user), [token, user]);
  const selectedCourse = useMemo(
    () => courses.find((course) => course.id === selectedCourseId) || null,
    [courses, selectedCourseId],
  );

  async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) {
        handleLogout();
      }
      throw new Error(payload.detail || `Request failed with HTTP ${response.status}`);
    }
    return payload as T;
  }

  async function loadMe() {
    const nextUser = await apiFetch<User>('/auth/me');
    setUser(nextUser);
  }

  async function loadCourses() {
    const payload = await apiFetch<{ courses: Course[] }>('/courses');
    setCourses(payload.courses);
    setSelectedCourseId((current) => {
      if (current && payload.courses.some((course) => course.id === current)) return current;
      return payload.courses[0]?.id ?? null;
    });
  }

  async function loadDocuments(courseId: number) {
    const payload = await apiFetch<{ documents: DocumentRecord[] }>(`/courses/${courseId}/documents`);
    setDocuments(payload.documents);
  }

  async function loadJob(jobId: number) {
    const job = await apiFetch<ProcessingJob>(`/jobs/${jobId}`);
    setActiveJob(job);
    return job;
  }

  useEffect(() => {
    if (!token) return;
    loadMe()
      .then(loadCourses)
      .catch((error) => {
        setMessage(error.message);
        handleLogout();
      });
  }, [token]);

  useEffect(() => {
    if (!isAuthenticated || !selectedCourseId) {
      setDocuments([]);
      return;
    }
    loadDocuments(selectedCourseId).catch((error) => setMessage(error.message));
  }, [isAuthenticated, selectedCourseId]);

  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') return;

    const timer = window.setInterval(async () => {
      try {
        const nextJob = await loadJob(activeJob.id);
        if (nextJob.course_id === selectedCourseId) {
          await loadDocuments(nextJob.course_id);
        }
      } catch (error) {
        setMessage(error instanceof Error ? error.message : 'Job refresh failed');
      }
    }, 900);

    return () => window.clearInterval(timer);
  }, [activeJob, selectedCourseId]);

  async function handleAuthSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const endpoint = authMode === 'login' ? '/auth/login' : '/auth/register';
      const payload = await apiFetch<{ access_token: string; username: string }>(endpoint, {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      localStorage.setItem(TOKEN_KEY, payload.access_token);
      setToken(payload.access_token);
      setPassword('');
      setMessage(authMode === 'login' ? 'Logged in.' : 'Account created.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken('');
    setUser(null);
    setCourses([]);
    setDocuments([]);
    setSelectedCourseId(null);
    setEditingId(null);
    setActiveJob(null);
    setSelectedFile(null);
    setCourseForm({ name: '', term: '', description: '' });
  }

  async function handleCourseSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      if (editingId) {
        const updated = await apiFetch<Course>(`/courses/${editingId}`, {
          method: 'PATCH',
          body: JSON.stringify(courseForm),
        });
        setSelectedCourseId(updated.id);
        setMessage('Course updated.');
      } else {
        const created = await apiFetch<Course>('/courses', {
          method: 'POST',
          body: JSON.stringify(courseForm),
        });
        setSelectedCourseId(created.id);
        setMessage('Course created.');
      }
      setCourseForm({ name: '', term: '', description: '' });
      setEditingId(null);
      await loadCourses();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Course save failed');
    } finally {
      setLoading(false);
    }
  }

  function startEdit(course: Course) {
    setEditingId(course.id);
    setCourseForm({
      name: course.name,
      term: course.term,
      description: course.description,
    });
  }

  async function deleteCourse(courseId: number) {
    if (!window.confirm('Delete this course?')) return;
    setLoading(true);
    setMessage('');
    try {
      await apiFetch(`/courses/${courseId}`, { method: 'DELETE' });
      if (editingId === courseId) {
        setEditingId(null);
        setCourseForm({ name: '', term: '', description: '' });
      }
      if (selectedCourseId === courseId) {
        setSelectedCourseId(null);
        setDocuments([]);
        setActiveJob(null);
      }
      await loadCourses();
      setMessage('Course deleted.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Delete failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleUploadSubmit(event: FormEvent) {
    event.preventDefault();
    if (!selectedCourseId || !selectedFile) {
      setMessage('Choose a course and a file first.');
      return;
    }

    setLoading(true);
    setMessage('');
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('material_type', materialType);

      const payload = await apiFetch<UploadResponse>(`/courses/${selectedCourseId}/documents`, {
        method: 'POST',
        body: formData,
      });

      setActiveJob(payload.job);
      setSelectedFile(null);
      const fileInput = document.getElementById('course-upload-input') as HTMLInputElement | null;
      if (fileInput) fileInput.value = '';
      await loadDocuments(selectedCourseId);
      setMessage('Upload started.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Student Workspace</p>
          <h1>Study Planner Agent</h1>
        </div>
        {isAuthenticated && user && (
          <div className="user-panel">
            <span>{user.username}</span>
            <button type="button" onClick={handleLogout}>Log out</button>
          </div>
        )}
      </section>

      {message && <div className="notice">{message}</div>}

      {!isAuthenticated ? (
        <section className="auth-layout">
          <div className="auth-copy">
            <h2>{authMode === 'login' ? 'Log in' : 'Create account'}</h2>
            <p>Access your courses and manage study materials in a student-scoped workspace.</p>
          </div>
          <form className="panel form-stack" onSubmit={handleAuthSubmit}>
            <label>
              Username
              <input value={username} onChange={(event) => setUsername(event.target.value)} required />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            <button type="submit" disabled={loading}>
              {loading ? 'Working...' : authMode === 'login' ? 'Log in' : 'Register'}
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
            >
              {authMode === 'login' ? 'Need an account? Register' : 'Already have an account? Log in'}
            </button>
          </form>
        </section>
      ) : (
        <section className="workspace-grid">
          <aside className="stack-column">
            <form className="panel form-stack" onSubmit={handleCourseSubmit}>
              <div className="section-heading">
                <h2>{editingId ? 'Edit course' : 'Create course'}</h2>
                {editingId && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => {
                      setEditingId(null);
                      setCourseForm({ name: '', term: '', description: '' });
                    }}
                  >
                    Cancel
                  </button>
                )}
              </div>
              <label>
                Course name
                <input
                  value={courseForm.name}
                  onChange={(event) => setCourseForm({ ...courseForm, name: event.target.value })}
                  placeholder="CS 412"
                  required
                />
              </label>
              <label>
                Term
                <input
                  value={courseForm.term}
                  onChange={(event) => setCourseForm({ ...courseForm, term: event.target.value })}
                  placeholder="Spring 2026"
                />
              </label>
              <label>
                Description
                <textarea
                  value={courseForm.description}
                  onChange={(event) => setCourseForm({ ...courseForm, description: event.target.value })}
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
                <button type="button" onClick={loadCourses}>Refresh</button>
              </div>
              {courses.length === 0 ? (
                <p className="empty-state">No courses yet. Create one to start organizing study materials.</p>
              ) : (
                <div className="course-list">
                  {courses.map((course) => (
                    <article
                      className={`course-card ${selectedCourseId === course.id ? 'is-selected' : ''}`}
                      key={course.id}
                    >
                      <button type="button" className="course-select" onClick={() => setSelectedCourseId(course.id)}>
                        <div>
                          <h3>{course.name}</h3>
                          {course.term && <p className="course-term">{course.term}</p>}
                          {course.description && <p>{course.description}</p>}
                        </div>
                      </button>
                      <div className="card-actions">
                        <button type="button" onClick={() => startEdit(course)}>Edit</button>
                        <button type="button" className="danger" onClick={() => deleteCourse(course.id)}>Delete</button>
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
              </div>

              <form className="form-stack" onSubmit={handleUploadSubmit}>
                <label>
                  Material type
                  <select value={materialType} onChange={(event) => setMaterialType(event.target.value)} disabled={!selectedCourse}>
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
                    onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
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
                {selectedCourse && <button type="button" onClick={() => loadDocuments(selectedCourse.id)}>Refresh</button>}
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
                        <p className="document-meta">Updated {formatDate(document.updated_at)}</p>
                      </div>
                      <span className={`status-badge status-${document.status}`}>{document.status}</span>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </section>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
