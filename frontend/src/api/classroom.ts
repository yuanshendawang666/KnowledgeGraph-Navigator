import http from './index'

export interface Classroom {
  id: number
  name: string
  description: string
  teacher_id: number
  invite_code: string
  member_count: number
  created_at: string
}

export interface ClassroomMember {
  id: number
  student_id: number
  username: string
  joined_at: string
}

export interface ClassroomStats {
  classroom_id: number
  member_count: number
  average_progress: number
  knowledge_points: Array<{
    knowledge_point_id: number
    name: string
    mastery_rate: number
    mastered_count: number
    total_students: number
  }>
}

export interface ClassroomTask {
  id: number
  title: string
  description: string
  course_id: number | null
  due_date: string | null
  created_at: string
  submitted_count?: number
  total_members?: number
  my_submitted?: boolean
  my_note?: string
  my_submitted_at?: string
}

export interface RankingItem {
  rank: number
  student_id: number
  username: string
  average_mastery: number
  mastered_count: number
  total_points: number
}

export interface Announcement {
  id: number
  title: string
  content: string
  author: string
  created_at: string
}

export interface Post {
  id: number
  title: string
  content: string
  author: string
  comment_count: number
  created_at: string
  comments: Array<{ id: number; content: string; author: string; created_at: string }>
}

export const classroomAPI = {
  list() {
    return http.get('/classrooms/') as Promise<Classroom[]>
  },

  create(data: { name: string; description?: string }) {
    return http.post('/classrooms/', data) as Promise<Classroom>
  },

  join(id: number, inviteCode: string) {
    return http.post(`/classrooms/${id}/join`, null, { params: { invite_code: inviteCode } }) as Promise<{ message: string }>
  },

  /** 仅凭邀请码加入班级（邀请码唯一） */
  joinByCode(inviteCode: string) {
    return http.post('/classrooms/join', null, { params: { invite_code: inviteCode } }) as Promise<{ message: string; classroom_id: number }>
  },

  remove(id: number) {
    return http.delete(`/classrooms/${id}`) as Promise<{ message: string }>
  },

  members(id: number) {
    return http.get(`/classrooms/${id}/members`) as Promise<ClassroomMember[]>
  },

  stats(id: number) {
    return http.get(`/classrooms/${id}/stats`) as Promise<ClassroomStats>
  },

  // ── 学习排名 ──
  ranking(id: number) {
    return http.get(`/classrooms/${id}/ranking`) as Promise<{ classroom_id: number; ranking: RankingItem[] }>
  },

  // ── 成员管理 ──
  removeMember(id: number, studentId: number) {
    return http.delete(`/classrooms/${id}/members/${studentId}`) as Promise<{ message: string }>
  },
  addMember(id: number, username: string) {
    return http.post(`/classrooms/${id}/members`, { username }) as Promise<{ message: string; student_id: number }>
  },

  // ── 课程关联 ──
  courses(id: number) {
    return http.get(`/classrooms/${id}/courses`) as Promise<Array<{ id: number; title: string; description: string }>>
  },
  addCourse(id: number, courseId: number) {
    return http.post(`/classrooms/${id}/courses`, { course_id: courseId }) as Promise<{ message: string }>
  },
  unlinkCourse(id: number, courseId: number) {
    return http.delete(`/classrooms/${id}/courses/${courseId}`) as Promise<{ message: string }>
  },

  // ── 学习任务闭环 ──
  tasks(id: number) {
    return http.get(`/classrooms/${id}/tasks`) as Promise<ClassroomTask[]>
  },
  createTask(id: number, data: { title: string; description?: string; course_id?: number | null; due_date?: string | null }) {
    return http.post(`/classrooms/${id}/tasks`, data) as Promise<ClassroomTask>
  },
  submitTask(id: number, taskId: number, note = '') {
    return http.post(`/classrooms/${id}/tasks/${taskId}/submit`, { note }) as Promise<{ message: string }>
  },
  taskSubmissions(id: number, taskId: number) {
    return http.get(`/classrooms/${id}/tasks/${taskId}/submissions`) as Promise<Array<{ id: number; student_id: number; username: string; note: string; submitted_at: string }>>
  },

  // ── 公告 ──
  announcements(id: number) {
    return http.get(`/classrooms/${id}/announcements`) as Promise<Announcement[]>
  },
  createAnnouncement(id: number, data: { title: string; content?: string }) {
    return http.post(`/classrooms/${id}/announcements`, data) as Promise<{ id: number; title: string }>
  },
  deleteAnnouncement(id: number, annId: number) {
    return http.delete(`/classrooms/${id}/announcements/${annId}`) as Promise<{ message: string }>
  },

  // ── 成绩导出 / AI 报告 ──
  exportCsv(id: number) {
    return http.get(`/classrooms/${id}/export`) as Promise<{ filename: string; csv: string }>
  },
  aiReport(id: number) {
    return http.post(`/classrooms/${id}/ai-report`) as Promise<{ report: string }>
  },

  // ── 讨论区 ──
  posts(id: number) {
    return http.get(`/classrooms/${id}/posts`) as Promise<Post[]>
  },
  createPost(id: number, data: { title: string; content?: string }) {
    return http.post(`/classrooms/${id}/posts`, data) as Promise<{ id: number; title: string }>
  },
  createComment(id: number, postId: number, content: string) {
    return http.post(`/classrooms/${id}/posts/${postId}/comments`, { content }) as Promise<{ message: string }>
  },
  deletePost(id: number, postId: number) {
    return http.delete(`/classrooms/${id}/posts/${postId}`) as Promise<{ message: string }>
  },
}
