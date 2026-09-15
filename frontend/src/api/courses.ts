import http from './index'
import axios from 'axios'

// 知识提取耗时较长（~100秒），单独建一个直连后端+长超时的实例
const directHttp = axios.create({
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' },
})
directHttp.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
directHttp.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (!err.response) throw new Error('NETWORK_ERROR')
    throw err
  }
)

export interface CourseItem {
  id: number
  title: string
  description: string
  teacher_id: number
  teacher_name?: string
  knowledge_point_count: number
  document_count: number
  created_at: string
  updated_at: string
}

export interface CourseDetail extends CourseItem {
  knowledge_points?: KnowledgePointItem[]
}

export interface KnowledgePointItem {
  id: number
  neo4j_node_id: string
  name: string
  description: string
  order_index: number
  level?: number
  is_module?: boolean
}

export interface TreeNode {
  id: string; label: string; description?: string; order_index: number
  level: number; is_module: boolean; status?: string; mastery_level?: number
  parent_id?: string | null; sqlite_id?: number; children: TreeNode[]
}

export interface GraphData {
  nodes: Array<{
    id: string; label: string; description?: string; order_index: number
    level?: number; is_module?: boolean; status?: string; mastery_level?: number
    sqlite_id?: number
  }>
  edges: Array<{ source: string; target: string; relation: string }>
  tree_edges?: Array<{ source: string; target: string; relation: string }>
  cross_edges?: Array<{ source: string; target: string; relation: string }>
  tree?: TreeNode[]
}

export interface ExtractResult {
  message: string
  knowledge_points_count: number
  relations_count: number
}

export const coursesAPI = {
  getList() {
    return http.get('/courses/') as Promise<CourseItem[]>
  },

  getDetail(id: number) {
    return http.get(`/courses/${id}`) as Promise<CourseDetail>
  },

  create(data: { title: string; description: string }) {
    return http.post('/courses/', data) as Promise<CourseItem>
  },

  update(id: number, data: { title?: string; description?: string }) {
    return http.put(`/courses/${id}`, data) as Promise<CourseItem>
  },

  delete(id: number) {
    return http.delete(`/courses/${id}`) as Promise<{ message: string }>
  },

  uploadDocument(courseId: number, file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return http.post(`/courses/${courseId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }) as Promise<{ message: string; filename: string; document_id: number }>
  },

  extractKnowledge(courseId: number) {
    // 直连后端，不走 Vite 代理，避免代理超时
    return directHttp.post(`http://localhost:8000/api/courses/${courseId}/extract`) as Promise<ExtractResult>
  },

  getGraph(courseId: number, depth = 2) {
    return http.get(`/courses/${courseId}/graph`, { params: { depth } }) as Promise<GraphData>
  },

  deleteGraph(courseId: number) {
    return http.delete(`/courses/${courseId}/graph`) as Promise<{ message: string }>
  },

  getDocuments(courseId: number) {
    return http.get(`/courses/${courseId}/documents`) as Promise<DocumentItem[]>
  },

  getDocument(courseId: number, docId: number) {
    return http.get(`/courses/${courseId}/documents/${docId}`) as Promise<{
      id: number; filename: string; status: string
      parsed_content: string; parsed_length: number; created_at: string
    }>
  },

  deleteDocument(courseId: number, docId: number) {
    return http.delete(`/courses/${courseId}/documents/${docId}`) as Promise<{ message: string }>
  },
}

export interface DocumentItem {
  id: number
  filename: string
  status: string
  parsed_length: number
  created_at: string
}
