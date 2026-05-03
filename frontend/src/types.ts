export type AuthMode = 'login' | 'register';

export type User = {
  id: number;
  username: string;
  created_at: string;
};

export type Course = {
  id: number;
  name: string;
  term: string;
  description: string;
  created_at: string;
  updated_at: string;
};

export type CourseForm = {
  name: string;
  term: string;
  description: string;
};

export type DocumentRecord = {
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

export type JobStep = {
  step: string;
  status: string;
  message: string;
};

export type ProcessingJob = {
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

export type UploadResponse = {
  document: DocumentRecord;
  job: ProcessingJob;
};

export type ParentChunk = {
  id: number;
  page_number: number | null;
  section_title: string;
  root_chunk_id: string;
  chunk_level: number;
  chunk_index: number;
  text: string;
};

export type ChildChunk = {
  id: number;
  parent_chunk_id: number;
  page_number: number | null;
  section_title: string;
  chunk_id: string;
  root_chunk_id: string;
  chunk_level: number;
  chunk_index: number;
  text: string;
};

export type DocumentChunkSummary = {
  document_id: number;
  parent_chunks: ParentChunk[];
  child_chunks: ChildChunk[];
};

export type ChunkRoute = {
  courseId: number;
  documentId: number;
};

export type SearchResult = {
  chunk_id: string;
  root_chunk_id: string;
  parent_chunk_id: number;
  document_id: number;
  filename: string;
  material_type: string;
  page_number: number | null;
  section_title: string;
  text: string;
  score: number;
};

export type SearchResponse = {
  query: string;
  retrieval_mode: string;
  results: SearchResult[];
};
