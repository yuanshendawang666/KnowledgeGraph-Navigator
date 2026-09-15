import http from './index'

export type QuestionType = 'single_choice' | 'multiple_choice' | 'true_false'
export type QuizMode = 'adaptive' | 'knowledge_point' | 'wrong_book'
export type QuestionDifficulty = 'basic' | 'advanced'

export interface QuizQuestion {
  id: number
  knowledge_point_id: number
  knowledge_point_name: string
  question_type: QuestionType
  difficulty: string
  content: string
  options: string[]
  order_index: number
}

export interface QuizSession {
  session_id: number
  course_id: number
  mode: QuizMode
  difficulty: string
  total_count: number
  questions: QuizQuestion[]
}

export interface AnswerResult {
  question_id: number
  is_correct: boolean
  score: number
  correct_answer: string
  explanation: string
  user_answer: string
}

export interface SubmitResult {
  session_id: number
  total_count: number
  correct_count: number
  score: number
  mastery_threshold: number
  results: AnswerResult[]
  progress_updates: Array<{
    knowledge_point_id: number
    status: string
    mastery_level: number
    accuracy: number
    mastered: boolean
  }>
}

export interface WrongBookItem {
  wrong_id: number
  question_id: number
  knowledge_point_id: number
  knowledge_point_name: string
  content: string
  question_type: QuestionType
  wrong_count: number
  last_wrong_at: string
}

export interface SessionHistoryItem {
  session_id: number
  mode: string
  difficulty: string
  total_count: number
  correct_count: number
  score: number
  status: string
  started_at: string
  finished_at: string | null
}

export interface SessionReview {
  session_id: number
  course_id: number
  mode: string
  difficulty: string
  total_count: number
  correct_count: number
  score: number
  status: string
  started_at: string
  finished_at: string | null
  questions: Array<{
    question_id: number
    knowledge_point_name: string
    question_type: string
    content: string
    options: string[]
    correct_answer: string
    explanation: string
    user_answer: string
    is_correct: boolean
    order_index: number
  }>
}

export const quizAPI = {
  generate(data: {
    course_id: number
    mode?: QuizMode
    knowledge_point_ids?: number[]
    difficulty?: QuestionDifficulty
    count?: number
  }) {
    return http.post('/quiz/generate', data) as Promise<QuizSession>
  },

  getSession(sessionId: number) {
    return http.get(`/quiz/session/${sessionId}`) as Promise<QuizSession>
  },

  submit(sessionId: number, answers: Array<{ question_id: number; user_answer: string }>) {
    return http.post(`/quiz/session/${sessionId}/submit`, { answers }) as Promise<SubmitResult>
  },

  getWrongBook(courseId: number) {
    return http.get(`/quiz/wrong-book/${courseId}`) as Promise<{
      course_id: number
      total: number
      items: WrongBookItem[]
    }>
  },

  /** 获取练习历史列表 */
  getSessions(courseId: number) {
    return http.get(`/quiz/sessions/${courseId}`) as Promise<SessionHistoryItem[]>
  },

  /** 获取已完成练习的详细回顾（含答案与解析） */
  reviewSession(sessionId: number) {
    return http.get(`/quiz/session/${sessionId}/review`) as Promise<SessionReview>
  },

  // ── 教师题库管理（功能8） ──
  generateQuestions(data: { course_id: number; knowledge_point_id: number; difficulty?: QuestionDifficulty; count?: number }) {
    return http.post('/quiz/questions/generate', data) as Promise<{
      generated: number
      questions: Array<{ id: number; content: string; question_type: string; difficulty: string; options: string[] }>
    }>
  },

  listQuestions(courseId: number, params?: { kp_id?: number; difficulty?: QuestionDifficulty }) {
    return http.get('/quiz/questions/', { params: { course_id: courseId, ...params } }) as Promise<Array<{
      id: number
      knowledge_point_id: number
      knowledge_point_name: string
      question_type: string
      difficulty: string
      content: string
      options: string[]
      correct_answer: string
      explanation: string
      source: string
      is_active: boolean
      created_at: string
    }>>
  },

  updateQuestion(id: number, data: {
    content?: string
    options?: string[]
    correct_answer?: string
    explanation?: string
    difficulty?: QuestionDifficulty
    is_active?: boolean
  }) {
    return http.put(`/quiz/questions/${id}`, data) as Promise<{ id: number; message: string }>
  },

  deleteQuestion(id: number) {
    return http.delete(`/quiz/questions/${id}`) as Promise<{ message: string }>
  },

  questionStats(courseId: number) {
    return http.get('/quiz/questions/stats', { params: { course_id: courseId } }) as Promise<{
      course_id: number
      total: number
      items: Array<{ question_id: number; content: string; knowledge_point_id: number; attempt_count: number; correct_count: number; accuracy: number; is_active: boolean }>
    }>
  },

  reviewQuestions(questionIds: number[], action: 'approve' | 'reject' = 'approve') {
    return http.post('/quiz/questions/review', { question_ids: questionIds, action }) as Promise<{ message: string }>
  },
}
