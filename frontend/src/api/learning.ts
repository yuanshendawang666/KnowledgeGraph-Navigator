import http from './index'

export type KnowledgeStatus = 'not_started' | 'in_progress' | 'mastered'

export interface ProgressRecord {
  knowledge_point_id: number
  knowledge_point_name: string
  neo4j_node_id: string
  status: KnowledgeStatus
  mastery_level: number
  updated_at: string
}

export interface CourseStats {
  total: number
  not_started: number
  in_progress: number
  mastered: number
  progress_percentage: number
}

export interface RecommendedPath {
  recommended: Array<{
    neo4j_node_id: string
    name: string
    description: string
    reason: string
    status: KnowledgeStatus
  }>
  total_available: number
  progress_summary: {
    total: number
    mastered: number
    percentage: number
  }
}

export const learningAPI = {
  getProgress(courseId: number) {
    return http.get(`/learning/progress/${courseId}`) as Promise<{
      course_id: number
      records: ProgressRecord[]
      stats: CourseStats
    }>
  },

  updateProgress(data: {
    knowledge_point_id: number
    status: KnowledgeStatus
    mastery_level?: number
  }) {
    return http.post('/learning/progress', data) as Promise<ProgressRecord>
  },

  batchUpdateProgress(data: Array<{
    knowledge_point_id: number
    status: KnowledgeStatus
    mastery_level?: number
  }>) {
    return http.post('/learning/progress/batch', data) as Promise<ProgressRecord[]>
  },

  getStats(courseId: number) {
    return http.get(`/learning/stats/${courseId}`) as Promise<CourseStats>
  },

  getRecommend(courseId: number) {
    return http.get(`/learning/recommend/${courseId}`) as Promise<RecommendedPath>
  },

  getNextRecommend(courseId: number, count = 3) {
    return http.get(`/learning/next/${courseId}`, { params: { count } }) as Promise<RecommendedPath>
  },

  getRecommendV2(courseId: number) {
    return http.get(`/learning/recommend-v2/${courseId}`) as Promise<{
      course_id: number
      profile_note: string
      total_count: number
      mastered_count: number
      progress_percentage: number
      recommendations: Array<{
        id: string
        name: string
        description: string
        reason: string
        confidence: number
        estimated_minutes: number
      }>
    }>
  },

  evaluateStart(knowledgePointId: number) {
    return http.post('/learning/evaluate/start', { knowledge_point_id: knowledgePointId }) as Promise<{
      eval_id: string
      question: string
      round: number
    }>
  },

  evaluateReply(evalId: string, answer: string) {
    return http.post('/learning/evaluate/reply', { eval_id: evalId, answer }) as Promise<{
      status: 'continue' | 'final'
      round?: number
      comment?: string
      question?: string
      mastery?: number
      mastery_level?: number
      learning_status?: string
      weak_points?: string[]
      suggestions?: string[]
    }>
  },

  getStudyMethods(courseId: number) {
    return http.get(`/learning/study-methods/${courseId}`) as Promise<{
      summary: string
      methods: Array<{ title: string; description: string; reason: string }>
    }>
  },
}
