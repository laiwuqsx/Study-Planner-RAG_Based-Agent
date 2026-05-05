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

export type Topic = {
  id: number;
  course_id: number;
  name: string;
  description: string;
  keywords: string[];
  importance: number;
  difficulty: number;
  status: string;
  quality_score: number;
  review_note: string;
  source_chunk_ids: string[];
  prerequisites: string[];
  created_at: string;
  updated_at: string;
};

export type StudyPlanItem = {
  id: number;
  topic_id: number;
  order_index: number;
  title: string;
  notes: string;
  focus_points: string[];
  context_snippets: string[];
  estimated_effort_minutes: number;
  importance: number;
  difficulty: number;
  source_chunk_count: number;
  created_at: string;
  updated_at: string;
};

export type StudyPlan = {
  id: number;
  course_id: number;
  title: string;
  summary: string;
  generation_mode: string;
  item_count: number;
  created_at: string;
  updated_at: string;
  items: StudyPlanItem[];
};

export type StudyPlanGenerateInput = {
  goal: string;
  sessions_per_week: number;
  minutes_per_session: number;
  topic_limit: number;
};

export type ChatSource = {
  chunk_id: string;
  document_id: number;
  filename: string;
  page_number: number | null;
  section_title: string;
  text: string;
  score: number;
};

export type ChatMessage = {
  id: number;
  role: string;
  content: string;
  retrieval_mode: string;
  sources: ChatSource[];
  created_at: string;
};

export type ChatSessionSummary = {
  id: number;
  course_id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatSessionDetail = {
  id: number;
  course_id: number;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
};

export type ChatResponse = {
  session: ChatSessionSummary;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
};
