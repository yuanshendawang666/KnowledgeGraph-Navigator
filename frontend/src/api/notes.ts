import http from './index'

export interface Note {
  id: number
  user_id: number
  username: string
  knowledge_point_id: number
  course_id: number
  title: string
  content: string
  tags: string
  is_public: boolean
  created_at: string
  updated_at: string
}

export const notesAPI = {
  list(params?: { kp_id?: number; course_id?: number }) {
    return http.get('/notes/', { params }) as Promise<Note[]>
  },

  create(data: {
    knowledge_point_id: number
    course_id: number
    title: string
    content?: string
    tags?: string
    is_public?: boolean
  }) {
    return http.post('/notes/', data) as Promise<Note>
  },

  update(id: number, data: {
    title?: string
    content?: string
    tags?: string
    is_public?: boolean
  }) {
    return http.put(`/notes/${id}`, data) as Promise<Note>
  },

  remove(id: number) {
    return http.delete(`/notes/${id}`) as Promise<{ message: string }>
  },

  listPublic(courseId: number) {
    return http.get(`/notes/`, { params: { course_id: courseId } }) as Promise<Note[]>
  },
}
