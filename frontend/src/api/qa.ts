import http from './index'

export interface QAAnswer {
  question: string
  answer: string
  /** 后端实际返回的参考知识点（键为 sources） */
  sources?: Array<{
    neo4j_id?: string | null
    name: string
    score?: number | null
  }>
  /** 旧版字段，兼容保留 */
  references?: Array<{
    knowledge_point_id: number
    name: string
    description: string
  }>
  suggested_questions: string[]
}

export const qaAPI = {
  ask(question: string, courseId?: number, sessionId?: number) {
    return http.post('/qa/ask', {
      question,
      course_id: courseId,
      session_id: sessionId,
    }) as Promise<QAAnswer & { session_id?: number }>
  },

  getRecommendQuestions() {
    return http.get('/qa/recommend-questions') as Promise<string[]>
  },
}
