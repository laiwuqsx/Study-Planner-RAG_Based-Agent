import React, { FormEvent, useEffect, useMemo, useState } from 'react';

import { AuthView } from './components/AuthView';
import { ChatView } from './components/ChatView';
import { DocumentChunksView } from './components/DocumentChunksView';
import { SearchView } from './components/SearchView';
import { TopicsView } from './components/TopicsView';
import { WorkspaceView } from './components/WorkspaceView';
import { API_BASE_URL, TOKEN_KEY } from './constants';
import { navigateToWorkspace, getCurrentRoute, type AppRoute } from './router';
import {
  AuthMode,
  ChatMessage,
  ChatResponse,
  ChatSessionDetail,
  ChatSessionSummary,
  Course,
  CourseForm,
  DocumentChunkSummary,
  DocumentRecord,
  ProcessingJob,
  SearchResponse,
  SearchResult,
  Topic,
  UploadResponse,
  User,
} from './types';

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => getCurrentRoute());
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
  const [chunkSummary, setChunkSummary] = useState<DocumentChunkSummary | null>(null);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [retrievalMode, setRetrievalMode] = useState('keyword');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [chatSessions, setChatSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatQuery, setChatQuery] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const isAuthenticated = useMemo(() => Boolean(token && user), [token, user]);
  const selectedCourse = useMemo(
    () => courses.find((course) => course.id === selectedCourseId) || null,
    [courses, selectedCourseId],
  );
  const routedDocument = useMemo(() => {
    if (route.name !== 'document-chunks') return null;
    return documents.find((document) => document.id === route.params.documentId) || null;
  }, [route, documents]);

  async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) handleLogout();
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
      if (route.name === 'document-chunks' || route.name === 'search' || route.name === 'topics' || route.name === 'chat') return route.params.courseId;
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

  async function loadDocumentChunks(courseId: number, documentId: number) {
    setChunkLoading(true);
    try {
      const payload = await apiFetch<DocumentChunkSummary>(`/courses/${courseId}/documents/${documentId}/chunks`);
      setChunkSummary(payload);
    } catch (error) {
      setChunkSummary(null);
      setMessage(error instanceof Error ? error.message : 'Chunk load failed');
    } finally {
      setChunkLoading(false);
    }
  }

  async function loadTopics(courseId: number) {
    setTopicsLoading(true);
    try {
      const payload = await apiFetch<{ topics: Topic[] }>(`/courses/${courseId}/topics`);
      setTopics(payload.topics);
    } catch (error) {
      setTopics([]);
      setMessage(error instanceof Error ? error.message : 'Topic load failed');
    } finally {
      setTopicsLoading(false);
    }
  }

  async function refreshTopics(courseId: number) {
    setTopicsLoading(true);
    setMessage('');
    try {
      const payload = await apiFetch<{ topics: Topic[]; topic_count: number }>(`/courses/${courseId}/topics/refresh`, {
        method: 'POST',
      });
      setTopics(payload.topics);
      await loadDocuments(courseId);
      setMessage(`Refreshed ${payload.topic_count} topics.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Topic refresh failed');
    } finally {
      setTopicsLoading(false);
    }
  }

  async function loadChatSessions(courseId: number) {
    const payload = await apiFetch<{ sessions: ChatSessionSummary[] }>(`/courses/${courseId}/sessions`);
    setChatSessions(payload.sessions);
  }

  async function loadChatSession(sessionId: number) {
    const payload = await apiFetch<ChatSessionDetail>(`/sessions/${sessionId}`);
    setActiveSessionId(payload.id);
    setChatMessages(payload.messages);
  }

  useEffect(() => {
    const onPopState = () => setRoute(getCurrentRoute());
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    if (!token) return;
    loadMe().then(loadCourses).catch((error) => {
      setMessage(error.message);
      handleLogout();
    });
  }, [token]);

  useEffect(() => {
    if (!isAuthenticated) {
      setDocuments([]);
      setChunkSummary(null);
      setSearchResults([]);
      setTopics([]);
      setChatSessions([]);
      setChatMessages([]);
      return;
    }
    const courseId = route.name === 'document-chunks' || route.name === 'search' || route.name === 'topics' || route.name === 'chat'
      ? route.params.courseId
      : selectedCourseId;
    if (!courseId) {
      setDocuments([]);
      setChunkSummary(null);
      setSearchResults([]);
      setTopics([]);
      setChatSessions([]);
      setChatMessages([]);
      return;
    }
    setSelectedCourseId(courseId);
    loadDocuments(courseId).catch((error) => setMessage(error.message));
  }, [isAuthenticated, selectedCourseId, route]);

  useEffect(() => {
    if (route.name !== 'document-chunks' || !isAuthenticated) {
      setChunkSummary(null);
      return;
    }
    loadDocumentChunks(route.params.courseId, route.params.documentId).catch((error) => setMessage(error.message));
  }, [route, isAuthenticated]);

  useEffect(() => {
    if (route.name !== 'search') {
      setSearchResults([]);
      return;
    }
  }, [route]);

  useEffect(() => {
    if (route.name !== 'topics' || !isAuthenticated) {
      setTopics([]);
      return;
    }
    loadTopics(route.params.courseId).catch((error) => setMessage(error.message));
  }, [route, isAuthenticated]);

  useEffect(() => {
    if (route.name !== 'chat' || !isAuthenticated) {
      setChatSessions([]);
      setChatMessages([]);
      setActiveSessionId(null);
      return;
    }
    loadChatSessions(route.params.courseId).catch((error) => setMessage(error.message));
  }, [route, isAuthenticated]);

  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') return;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await loadJob(activeJob.id);
        const courseId =
          route.name === 'document-chunks' || route.name === 'search' || route.name === 'topics' || route.name === 'chat'
            ? route.params.courseId
            : selectedCourseId;
        if (courseId && nextJob.course_id === courseId) {
          await loadDocuments(courseId);
          if (route.name === 'topics') {
            await loadTopics(courseId);
          }
          if (route.name === 'chat') {
            await loadChatSessions(courseId);
          }
        }
      } catch (error) {
        setMessage(error instanceof Error ? error.message : 'Job refresh failed');
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [activeJob, selectedCourseId, route]);

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
    setChunkSummary(null);
    setTopics([]);
    setChatSessions([]);
    setChatMessages([]);
    setActiveSessionId(null);
    setSelectedFile(null);
    setCourseForm({ name: '', term: '', description: '' });
    navigateToWorkspace();
  }

  async function handleSearchSubmit(event: FormEvent) {
    event.preventDefault();
    const courseId = route.name === 'search' ? route.params.courseId : selectedCourseId;
    if (!courseId || !searchQuery.trim()) return;

    setSearchLoading(true);
    setMessage('');
    try {
      const payload = await apiFetch<SearchResponse>(
        `/courses/${courseId}/search?query=${encodeURIComponent(searchQuery.trim())}&retrieval_mode=${retrievalMode}&top_k=8`,
      );
      setSearchResults(payload.results);
    } catch (error) {
      setSearchResults([]);
      setMessage(error instanceof Error ? error.message : 'Search failed');
    } finally {
      setSearchLoading(false);
    }
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
    setCourseForm({ name: course.name, term: course.term, description: course.description });
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
        setChunkSummary(null);
        setSearchResults([]);
        setTopics([]);
        setChatSessions([]);
        setChatMessages([]);
        setActiveSessionId(null);
        navigateToWorkspace();
      }
      await loadCourses();
      setMessage('Course deleted.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Delete failed');
    } finally {
      setLoading(false);
    }
  }

  async function deleteDocument(document: DocumentRecord) {
    const courseId = route.name === 'document-chunks' ? route.params.courseId : selectedCourseId;
    if (!courseId || !window.confirm('Delete this material?')) return;
    setLoading(true);
    setMessage('');
    try {
      await apiFetch(`/courses/${courseId}/documents/${document.id}`, { method: 'DELETE' });
      if (activeJob?.document_id === document.id) setActiveJob(null);
      if (route.name === 'document-chunks' && route.params.documentId === document.id) {
        setChunkSummary(null);
        navigateToWorkspace();
      }
      await loadDocuments(courseId);
      if (route.name === 'topics') {
        await loadTopics(courseId);
      }
      setMessage('Material deleted.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Delete failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleUploadSubmit(event: FormEvent) {
    event.preventDefault();
    const courseId = selectedCourseId;
    if (!courseId || !selectedFile) {
      setMessage('Choose a course and a file first.');
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('material_type', materialType);
      const payload = await apiFetch<UploadResponse>(`/courses/${courseId}/documents`, {
        method: 'POST',
        body: formData,
      });
      setActiveJob(payload.job);
      setSelectedFile(null);
      const fileInput = document.getElementById('course-upload-input') as HTMLInputElement | null;
      if (fileInput) fileInput.value = '';
      await loadDocuments(courseId);
      if (route.name === 'topics') {
        await loadTopics(courseId);
      }
      setMessage('Upload started.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleChatSubmit(event: FormEvent) {
    event.preventDefault();
    const courseId = route.name === 'chat' ? route.params.courseId : selectedCourseId;
    if (!courseId || !chatQuery.trim()) return;
    setChatLoading(true);
    setMessage('');
    try {
      const payload = await apiFetch<ChatResponse>(`/courses/${courseId}/chat`, {
        method: 'POST',
        body: JSON.stringify({
          message: chatQuery.trim(),
          session_id: activeSessionId,
          retrieval_mode: retrievalMode,
          top_k: 5,
        }),
      });
      setActiveSessionId(payload.session.id);
      setChatMessages((current) =>
        current.length > 0 && activeSessionId === payload.session.id
          ? [...current, payload.user_message, payload.assistant_message]
          : [payload.user_message, payload.assistant_message],
      );
      setChatQuery('');
      await loadChatSessions(courseId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Chat failed');
    } finally {
      setChatLoading(false);
    }
  }

  async function handleDeleteSession(sessionId: number) {
    if (!window.confirm('Delete this chat session?')) return;
    setMessage('');
    try {
      await apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setChatMessages([]);
      }
      const courseId = route.name === 'chat' ? route.params.courseId : selectedCourseId;
      if (courseId) {
        await loadChatSessions(courseId);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Session delete failed');
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
        <AuthView
          authMode={authMode}
          username={username}
          password={password}
          loading={loading}
          onSubmit={handleAuthSubmit}
          onUsernameChange={setUsername}
          onPasswordChange={setPassword}
          onToggleMode={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
        />
      ) : route.name === 'search' ? (
        <SearchView
          course={selectedCourse}
          query={searchQuery}
          retrievalMode={retrievalMode}
          results={searchResults}
          loading={searchLoading}
          onQueryChange={setSearchQuery}
          onRetrievalModeChange={setRetrievalMode}
          onSubmit={handleSearchSubmit}
        />
      ) : route.name === 'topics' ? (
        <TopicsView
          course={selectedCourse}
          topics={topics}
          loading={topicsLoading}
          onRefresh={() => route.name === 'topics' && refreshTopics(route.params.courseId)}
        />
      ) : route.name === 'chat' ? (
        <ChatView
          course={selectedCourse}
          sessions={chatSessions}
          activeSessionId={activeSessionId}
          messages={chatMessages}
          query={chatQuery}
          retrievalMode={retrievalMode}
          loading={chatLoading}
          onNewSession={() => {
            setActiveSessionId(null);
            setChatMessages([]);
          }}
          onSelectSession={(sessionId) => loadChatSession(sessionId).catch((error) => setMessage(error.message))}
          onDeleteSession={handleDeleteSession}
          onQueryChange={setChatQuery}
          onRetrievalModeChange={setRetrievalMode}
          onSubmit={handleChatSubmit}
        />
      ) : route.name === 'document-chunks' ? (
        <DocumentChunksView
          course={selectedCourse}
          document={routedDocument}
          chunkSummary={chunkSummary}
          loading={chunkLoading}
          onBack={navigateToWorkspace}
        />
      ) : (
        <WorkspaceView
          courses={courses}
          selectedCourseId={selectedCourseId}
          courseForm={courseForm}
          editingId={editingId}
          documents={documents}
          selectedFile={selectedFile}
          materialType={materialType}
          activeJob={activeJob}
          loading={loading}
          onCourseSubmit={handleCourseSubmit}
          onCourseFormChange={setCourseForm}
          onCancelEdit={() => {
            setEditingId(null);
            setCourseForm({ name: '', term: '', description: '' });
          }}
          onRefreshCourses={loadCourses}
          onSelectCourse={setSelectedCourseId}
          onStartEdit={startEdit}
          onDeleteCourse={deleteCourse}
          onUploadSubmit={handleUploadSubmit}
          onMaterialTypeChange={setMaterialType}
          onFileChange={setSelectedFile}
          onRefreshDocuments={() => selectedCourseId && loadDocuments(selectedCourseId)}
          onDeleteDocument={deleteDocument}
        />
      )}
    </main>
  );
}
