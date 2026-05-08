import React, { FormEvent, useEffect, useMemo, useState } from 'react';

import { AuthView } from './components/AuthView';
import { ChatView } from './components/ChatView';
import { DocumentChunksView } from './components/DocumentChunksView';
import { SearchView } from './components/SearchView';
import { StudyPlanView } from './components/StudyPlanView';
import { TopicReviewView } from './components/TopicReviewView';
import { TopicsView } from './components/TopicsView';
import { WorkspaceView } from './components/WorkspaceView';
import { API_BASE_URL, TOKEN_KEY } from './constants';
import {
  navigateToChat,
  navigateToSearch,
  navigateToStudyPlan,
  navigateToTopics,
  navigateToWorkspace,
  getCurrentRoute,
  type AppRoute,
} from './router';
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
  StudyPlan,
  StudyPlanListResponse,
  StudyPlanGenerateInput,
  Topic,
  TopicReview,
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
  const [topicReview, setTopicReview] = useState<TopicReview | null>(null);
  const [topicReviewLoading, setTopicReviewLoading] = useState(false);
  const [topicReviewChatMessages, setTopicReviewChatMessages] = useState<ChatMessage[]>([]);
  const [topicReviewChatQuery, setTopicReviewChatQuery] = useState('');
  const [topicReviewChatLoading, setTopicReviewChatLoading] = useState(false);
  const [topicReviewSessionId, setTopicReviewSessionId] = useState<number | null>(null);
  const [topicPracticeLoading, setTopicPracticeLoading] = useState(false);
  const [studyPlans, setStudyPlans] = useState<StudyPlan[]>([]);
  const [activeStudyPlanId, setActiveStudyPlanId] = useState<number | null>(null);
  const [studyPlanLoading, setStudyPlanLoading] = useState(false);
  const [studyPlanForm, setStudyPlanForm] = useState<StudyPlanGenerateInput>({
    goal: 'Build a focused review plan for this course.',
    sessions_per_week: 4,
    minutes_per_session: 90,
    topic_limit: 10,
  });
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
  const activeNav = useMemo(() => {
    switch (route.name) {
      case 'workspace':
        return 'workspace';
      case 'topics':
      case 'topic-review':
        return 'topics';
      case 'study-plan':
        return 'study-plan';
      case 'chat':
        return 'chat';
      case 'search':
      case 'document-chunks':
        return 'search';
      default:
        return 'workspace';
    }
  }, [route]);

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
      if (route.name === 'document-chunks' || route.name === 'search' || route.name === 'topics' || route.name === 'topic-review' || route.name === 'chat' || route.name === 'study-plan') return route.params.courseId;
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

  async function loadTopicReview(courseId: number, topicId: number) {
    setTopicReviewLoading(true);
    try {
      const payload = await apiFetch<TopicReview>(`/courses/${courseId}/topics/${topicId}/review`);
      setTopicReview(payload);
    } catch (error) {
      setTopicReview(null);
      setMessage(error instanceof Error ? error.message : 'Topic review load failed');
    } finally {
      setTopicReviewLoading(false);
    }
  }

  async function loadStudyPlan(courseId: number) {
    setStudyPlanLoading(true);
    try {
      const payload = await apiFetch<StudyPlanListResponse>(`/courses/${courseId}/study-plan/all`);
      setStudyPlans(payload.plans);
      setActiveStudyPlanId((current) => {
        if (current && payload.plans.some((plan) => plan.id === current)) return current;
        return payload.plans[0]?.id ?? null;
      });
    } catch (error) {
      setStudyPlans([]);
      setActiveStudyPlanId(null);
      const detail = error instanceof Error ? error.message : 'Study plan load failed';
      if (detail !== 'Study plan not found') {
        setMessage(detail);
      }
    } finally {
      setStudyPlanLoading(false);
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
      setTopicReview(null);
      setStudyPlans([]);
      setActiveStudyPlanId(null);
      setChatSessions([]);
      setChatMessages([]);
      return;
    }
    const courseId = route.name === 'document-chunks' || route.name === 'search' || route.name === 'topics' || route.name === 'topic-review' || route.name === 'chat' || route.name === 'study-plan'
      ? route.params.courseId
      : selectedCourseId;
    if (!courseId) {
      setDocuments([]);
      setChunkSummary(null);
      setSearchResults([]);
      setTopics([]);
      setTopicReview(null);
      setStudyPlans([]);
      setActiveStudyPlanId(null);
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
    if (route.name !== 'topic-review' || !isAuthenticated) {
      setTopicReview(null);
      setTopicReviewChatMessages([]);
      setTopicReviewChatQuery('');
      setTopicReviewSessionId(null);
      return;
    }
    loadTopicReview(route.params.courseId, route.params.topicId).catch((error) => setMessage(error.message));
  }, [route, isAuthenticated]);

  useEffect(() => {
    if (route.name !== 'study-plan' || !isAuthenticated) {
      setStudyPlans([]);
      setActiveStudyPlanId(null);
      return;
    }
    loadStudyPlan(route.params.courseId).catch((error) => setMessage(error.message));
  }, [route, isAuthenticated]);

  useEffect(() => {
    if (route.name !== 'chat' || !isAuthenticated) {
      setChatSessions([]);
      setChatMessages([]);
      setActiveSessionId(null);
      return;
    }
    const presetQuery = new URLSearchParams(window.location.search).get('q');
    if (presetQuery) {
      setChatQuery(presetQuery);
    }
    loadChatSessions(route.params.courseId).catch((error) => setMessage(error.message));
  }, [route, isAuthenticated]);

  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') return;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await loadJob(activeJob.id);
        const courseId =
          route.name === 'document-chunks' ||
          route.name === 'search' ||
          route.name === 'topics' ||
          route.name === 'topic-review' ||
          route.name === 'chat' ||
          route.name === 'study-plan'
            ? route.params.courseId
            : selectedCourseId;
        if (courseId && nextJob.course_id === courseId) {
          const stepChanged = nextJob.current_step !== activeJob.current_step || nextJob.status !== activeJob.status;
          if (stepChanged) {
            await loadDocuments(courseId);
          }
          if (nextJob.status === 'completed') {
            if (route.name === 'topics') {
              await loadTopics(courseId);
            }
            if (route.name === 'study-plan') {
              await loadStudyPlan(courseId);
            }
            if (route.name === 'chat') {
              await loadChatSessions(courseId);
            }
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
    setTopicReview(null);
    setTopicReviewChatMessages([]);
    setTopicReviewChatQuery('');
    setTopicReviewSessionId(null);
    setStudyPlans([]);
    setActiveStudyPlanId(null);
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
        setTopicReview(null);
        setTopicReviewChatMessages([]);
        setTopicReviewChatQuery('');
        setTopicReviewSessionId(null);
        setStudyPlans([]);
        setActiveStudyPlanId(null);
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
      if (route.name === 'study-plan') {
        await loadStudyPlan(courseId);
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
      if (route.name === 'study-plan') {
        await loadStudyPlan(courseId);
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

  async function handleStudyPlanGenerate(path: '/generate' | '/regenerate') {
    const courseId = route.name === 'study-plan' ? route.params.courseId : selectedCourseId;
    if (!courseId) return;
    setStudyPlanLoading(true);
    setMessage('');
    try {
      const payload = await apiFetch<{ plan: StudyPlan }>(`/courses/${courseId}/study-plan${path}`, {
        method: 'POST',
        body: JSON.stringify(studyPlanForm),
      });
      setStudyPlans((current) => [payload.plan, ...current.filter((plan) => plan.id !== payload.plan.id)]);
      setActiveStudyPlanId(payload.plan.id);
      setMessage(path === '/generate' ? 'Study plan generated.' : 'Study plan regenerated.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Study plan generation failed');
    } finally {
      setStudyPlanLoading(false);
    }
  }

  async function handleTopicReviewChatSubmit(event: FormEvent) {
    event.preventDefault();
    const courseId = route.name === 'topic-review' ? route.params.courseId : selectedCourseId;
    const topicName = topicReview?.topic.name;
    if (!courseId || !topicReview || !topicReviewChatQuery.trim()) return;
    setTopicReviewChatLoading(true);
    setMessage('');
    try {
      const payload = await apiFetch<ChatResponse>(`/courses/${courseId}/chat`, {
        method: 'POST',
        body: JSON.stringify({
          message: `About the topic "${topicName}": ${topicReviewChatQuery.trim()}`,
          session_id: topicReviewSessionId,
          retrieval_mode: 'hybrid',
          top_k: 5,
        }),
      });
      setTopicReviewSessionId(payload.session.id);
      setTopicReviewChatMessages((current) => [...current, payload.user_message, payload.assistant_message]);
      setTopicReviewChatQuery('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Topic review chat failed');
    } finally {
      setTopicReviewChatLoading(false);
    }
  }

  async function handleTopicMasteryChange(status: 'not_started' | 'reviewing' | 'mastered') {
    const courseId = route.name === 'topic-review' ? route.params.courseId : selectedCourseId;
    const topicId = route.name === 'topic-review' ? route.params.topicId : topicReview?.topic.id;
    if (!courseId || !topicId) return;
    setMessage('');
    try {
      const payload = await apiFetch<Topic>(`/courses/${courseId}/topics/${topicId}/mastery`, {
        method: 'PATCH',
        body: JSON.stringify({ mastery_status: status }),
      });
      setTopicReview((current) => (current ? { ...current, topic: payload } : current));
      setTopics((current) => current.map((topic) => (topic.id === payload.id ? payload : topic)));
      setMessage(`Topic marked as ${status.replace('_', ' ')}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Topic status update failed');
    }
  }

  async function handleStudyPlanItemStatusChange(itemId: number, status: 'pending' | 'in_progress' | 'completed') {
    const courseId = route.name === 'study-plan' ? route.params.courseId : selectedCourseId;
    if (!courseId) return;
    setStudyPlanLoading(true);
    setMessage('');
    try {
      const payload = await apiFetch<StudyPlan>(`/courses/${courseId}/study-plan/items/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      setStudyPlans((current) => current.map((plan) => (plan.id === payload.id ? payload : plan)));
      setActiveStudyPlanId(payload.id);
      setMessage(`Study plan item marked ${status.replace('_', ' ')}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Study plan item update failed');
    } finally {
      setStudyPlanLoading(false);
    }
  }

  async function handleDeleteStudyPlan(planId: number) {
    const courseId = route.name === 'study-plan' ? route.params.courseId : selectedCourseId;
    if (!courseId || !window.confirm('Delete this saved study plan?')) return;
    setStudyPlanLoading(true);
    setMessage('');
    try {
      await apiFetch(`/courses/${courseId}/study-plan/${planId}`, { method: 'DELETE' });
      setStudyPlans((current) => {
        const nextPlans = current.filter((plan) => plan.id !== planId);
        setActiveStudyPlanId((currentActive) => {
          if (currentActive !== planId) return currentActive;
          return nextPlans[0]?.id ?? null;
        });
        return nextPlans;
      });
      setMessage('Study plan deleted.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Study plan delete failed');
    } finally {
      setStudyPlanLoading(false);
    }
  }

  function handleSelectStudyPlan(planId: number) {
    setActiveStudyPlanId((current) => (current === planId ? null : planId));
  }

  async function handleRefreshTopicPracticeQuestions() {
    const courseId = route.name === 'topic-review' ? route.params.courseId : selectedCourseId;
    const topicId = route.name === 'topic-review' ? route.params.topicId : topicReview?.topic.id;
    if (!courseId || !topicId) return;
    setTopicPracticeLoading(true);
    setMessage('');
    try {
      const payload = await apiFetch<{ topic_id: number; questions: TopicReview['practice_questions'] }>(
        `/courses/${courseId}/topics/${topicId}/practice-questions`,
        { method: 'POST' },
      );
      setTopicReview((current) => (current ? { ...current, practice_questions: payload.questions } : current));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Practice question generation failed');
    } finally {
      setTopicPracticeLoading(false);
    }
  }

  function navigateFromTopbar(destination: 'workspace' | 'topics' | 'study-plan' | 'chat' | 'search') {
    if (destination === 'workspace') {
      navigateToWorkspace();
      return;
    }
    if (!selectedCourseId) return;
    if (destination === 'topics') navigateToTopics(selectedCourseId);
    if (destination === 'study-plan') navigateToStudyPlan(selectedCourseId);
    if (destination === 'chat') navigateToChat(selectedCourseId);
    if (destination === 'search') navigateToSearch(selectedCourseId);
  }

  function handleTopbarCourseChange(courseId: number) {
    setSelectedCourseId(courseId);
    if (route.name === 'workspace') return;
    if (route.name === 'topics' || route.name === 'topic-review') {
      navigateToTopics(courseId);
      return;
    }
    if (route.name === 'study-plan') {
      navigateToStudyPlan(courseId);
      return;
    }
    if (route.name === 'chat') {
      navigateToChat(courseId);
      return;
    }
    if (route.name === 'search' || route.name === 'document-chunks') {
      navigateToSearch(courseId);
    }
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div className="topbar-brand">
          <div>
            <h1>Study Planner Agent</h1>
            <p className="topbar-subtitle">Course materials, topic review, study plans, and grounded chat in one place.</p>
          </div>
        </div>
        {isAuthenticated && user && (
          <div className="user-panel">
            <div className="course-switcher">
              <label className="course-switcher-label" htmlFor="topbar-course-select">
                Course
              </label>
              <select
                id="topbar-course-select"
                value={selectedCourseId ?? ''}
                onChange={(event) => handleTopbarCourseChange(Number(event.target.value))}
                disabled={courses.length === 0}
              >
                {courses.length === 0 ? (
                  <option value="">No courses</option>
                ) : (
                  courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.term ? `${course.name} · ${course.term}` : course.name}
                    </option>
                  ))
                )}
              </select>
            </div>
            <div className="user-meta">
              <span>{user.username}</span>
              <p>{selectedCourse?.term || 'Choose a course to unlock every workspace view.'}</p>
            </div>
            <button type="button" className="secondary-button" onClick={handleLogout}>Log out</button>
          </div>
        )}
      </section>

      {isAuthenticated && (
        <nav className="app-nav" aria-label="Primary">
          <button
            type="button"
            className={`nav-link ${activeNav === 'workspace' ? 'is-active' : ''}`}
            onClick={() => navigateFromTopbar('workspace')}
          >
            Workspace
          </button>
          <button
            type="button"
            className={`nav-link ${activeNav === 'topics' ? 'is-active' : ''}`}
            onClick={() => navigateFromTopbar('topics')}
            disabled={!selectedCourseId}
          >
            Topics
          </button>
          <button
            type="button"
            className={`nav-link ${activeNav === 'study-plan' ? 'is-active' : ''}`}
            onClick={() => navigateFromTopbar('study-plan')}
            disabled={!selectedCourseId}
          >
            Study Plan
          </button>
          <button
            type="button"
            className={`nav-link ${activeNav === 'chat' ? 'is-active' : ''}`}
            onClick={() => navigateFromTopbar('chat')}
            disabled={!selectedCourseId}
          >
            Chat
          </button>
          <button
            type="button"
            className={`nav-link ${activeNav === 'search' ? 'is-active' : ''}`}
            onClick={() => navigateFromTopbar('search')}
            disabled={!selectedCourseId}
          >
            Search
          </button>
        </nav>
      )}

      {message && <div className="notice">{message}</div>}

      <section className="app-content">
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
        ) : route.name === 'topic-review' ? (
        <TopicReviewView
          course={selectedCourse}
          review={topicReview}
          loading={topicReviewLoading}
          practiceLoading={topicPracticeLoading}
          backTarget={new URLSearchParams(window.location.search).get('from') === 'study-plan' ? 'study-plan' : 'topics'}
          chatQuery={topicReviewChatQuery}
          chatLoading={topicReviewChatLoading}
          chatMessages={topicReviewChatMessages}
          onChatQueryChange={setTopicReviewChatQuery}
          onChatSubmit={handleTopicReviewChatSubmit}
          onMasteryChange={handleTopicMasteryChange}
          onRefreshPracticeQuestions={handleRefreshTopicPracticeQuestions}
        />
        ) : route.name === 'study-plan' ? (
        <StudyPlanView
          course={selectedCourse}
          plans={studyPlans}
          activePlanId={activeStudyPlanId}
          loading={studyPlanLoading}
          form={studyPlanForm}
          onFormChange={setStudyPlanForm}
          onGenerate={(event) => {
            event.preventDefault();
            handleStudyPlanGenerate('/generate').catch((error) => setMessage(error.message));
          }}
          onRegenerate={() => handleStudyPlanGenerate('/regenerate').catch((error) => setMessage(error.message))}
          onSelectPlan={handleSelectStudyPlan}
          onDeletePlan={handleDeleteStudyPlan}
          onItemStatusChange={handleStudyPlanItemStatusChange}
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
      </section>
    </main>
  );
}
