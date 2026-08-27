import http from './index'

export interface ChatSession {
  id: number; title: string; course_id: number | null
  created_at: string; updated_at: string; msg_count: number
}

export const chatAPI = {
  createSession(courseId?: number, title = '新对话') {
    const params = courseId != null ? `?course_id=${courseId}&title=${encodeURIComponent(title)}` : `?title=${encodeURIComponent(title)}`
    return http.post(`/chat/sessions${params}`) as Promise<ChatSession>
  },
  listSessions(courseId?: number) {
    const params = courseId ? `?course_id=${courseId}` : ''
    return http.get(`/chat/sessions${params}`) as Promise<ChatSession[]>
  },
  getMessages(sessionId: number) {
    return http.get(`/chat/sessions/${sessionId}/messages`) as Promise<Array<{id:number;role:string;content:string;references_json:string;created_at:string}>>
  },
  deleteSession(sessionId: number) {
    return http.delete(`/chat/sessions/${sessionId}`) as Promise<{message:string}>
  },
  renameSession(sessionId: number, title: string) {
    return http.put(`/chat/sessions/${sessionId}?title=${encodeURIComponent(title)}`) as Promise<{message:string}>
  },
  exportMarkdown(sessionId: number) {
    return http.get(`/chat/sessions/${sessionId}/export/markdown`, { responseType: 'text' }) as Promise<string>
  },
  exportPdf(sessionId: number) {
    return http.get(`/chat/sessions/${sessionId}/export/pdf`, { responseType: 'blob' }) as Promise<Blob>
  },
}
