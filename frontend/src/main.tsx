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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'studyPlannerToken';

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || '');
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [courses, setCourses] = useState<Course[]>([]);
  const [courseForm, setCourseForm] = useState<CourseForm>({ name: '', term: '', description: '' });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const isAuthenticated = useMemo(() => Boolean(token && user), [token, user]);

  async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (!headers.has('Content-Type') && options.body) {
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
    setEditingId(null);
    setCourseForm({ name: '', term: '', description: '' });
  }

  async function handleCourseSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      if (editingId) {
        await apiFetch<Course>(`/courses/${editingId}`, {
          method: 'PATCH',
          body: JSON.stringify(courseForm),
        });
        setMessage('Course updated.');
      } else {
        await apiFetch<Course>('/courses', {
          method: 'POST',
          body: JSON.stringify(courseForm),
        });
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
      await loadCourses();
      setMessage('Course deleted.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Delete failed');
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
                  <article className="course-card" key={course.id}>
                    <div>
                      <h3>{course.name}</h3>
                      {course.term && <p className="course-term">{course.term}</p>}
                      {course.description && <p>{course.description}</p>}
                    </div>
                    <div className="card-actions">
                      <button type="button" onClick={() => startEdit(course)}>Edit</button>
                      <button type="button" className="danger" onClick={() => deleteCourse(course.id)}>Delete</button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
