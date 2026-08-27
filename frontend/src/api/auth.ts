import http from './index'

export interface UserInfo {
  id: number
  username: string
  email: string
  role: 'student' | 'teacher'
  major?: string
  grade?: string
  learning_goal?: string
  created_at?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserInfo
}

export const authAPI = {
  register(data: { username: string; email: string; password: string; role?: string }) {
    return http.post('/auth/register', data) as Promise<TokenResponse>
  },

  login(data: { username: string; password: string }) {
    return http.post('/auth/login', data) as Promise<TokenResponse>
  },

  getMe() {
    return http.get('/auth/me') as Promise<UserInfo>
  },

  updateMe(data: {
    username?: string
    email?: string
    major?: string
    grade?: string
    learning_goal?: string
  }) {
    return http.put('/auth/me', data) as Promise<UserInfo>
  },
}
