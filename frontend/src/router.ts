import { ChunkRoute } from './types';

export type AppRoute =
  | { name: 'workspace' }
  | { name: 'search'; params: { courseId: number } }
  | { name: 'topics'; params: { courseId: number } }
  | { name: 'chat'; params: { courseId: number } }
  | { name: 'document-chunks'; params: ChunkRoute };

export function getCurrentRoute(): AppRoute {
  const path = window.location.pathname;
  const searchMatch = path.match(/^\/courses\/(\d+)\/search$/);
  if (searchMatch) {
    return {
      name: 'search',
      params: { courseId: Number(searchMatch[1]) },
    };
  }
  const topicsMatch = path.match(/^\/courses\/(\d+)\/topics$/);
  if (topicsMatch) {
    return {
      name: 'topics',
      params: { courseId: Number(topicsMatch[1]) },
    };
  }
  const chatMatch = path.match(/^\/courses\/(\d+)\/chat$/);
  if (chatMatch) {
    return {
      name: 'chat',
      params: { courseId: Number(chatMatch[1]) },
    };
  }
  const match = path.match(/^\/courses\/(\d+)\/documents\/(\d+)\/chunks$/);
  if (match) {
    return {
      name: 'document-chunks',
      params: {
        courseId: Number(match[1]),
        documentId: Number(match[2]),
      },
    };
  }
  return { name: 'workspace' };
}

export function navigateToWorkspace() {
  window.history.pushState({}, '', '/');
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function navigateToSearch(courseId: number) {
  window.history.pushState({}, '', `/courses/${courseId}/search`);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function navigateToTopics(courseId: number) {
  window.history.pushState({}, '', `/courses/${courseId}/topics`);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function navigateToChat(courseId: number) {
  window.history.pushState({}, '', `/courses/${courseId}/chat`);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function navigateToDocumentChunks(courseId: number, documentId: number) {
  window.history.pushState({}, '', `/courses/${courseId}/documents/${documentId}/chunks`);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
