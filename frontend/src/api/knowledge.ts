import http from './index'

export interface KnowledgeNeighbor {
  id: number
  neo4j_id: string
  name: string
  relation: string
  direction: 'out' | 'in'
}

export interface KnowledgeDetail {
  id: number
  name: string
  description: string
  neo4j_node_id: string | null
  level: number
  is_module: boolean
  parent_id: number | null
  course_id: number
  course_title: string
  status: 'not_started' | 'in_progress' | 'mastered'
  mastery_level: number
  neighbors: KnowledgeNeighbor[]
  documents: Array<{ id: number; filename: string; status: string }>
  notes: Array<{
    id: number
    user_id: number
    username: string
    title: string
    content: string
    is_public: boolean
    created_at: string
  }>
}

export interface AIContent {
  explanation: string
  examples: string[]
  pitfalls: string[]
}

export const knowledgeAPI = {
  detail(id: number) {
    return http.get(`/knowledge/${id}`) as Promise<KnowledgeDetail>
  },

  aiContent(id: number) {
    return http.post(`/knowledge/${id}/ai-content`) as Promise<AIContent>
  },
}
