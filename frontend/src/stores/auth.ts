import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI, type UserInfo } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const token = ref<string | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isTeacher = computed(() => user.value?.role === 'teacher')
  const isStudent = computed(() => user.value?.role === 'student')

  // 初始化 — 从 localStorage 恢复
  function initialize() {
    const savedToken = localStorage.getItem('token')
    const savedUser = localStorage.getItem('user')
    if (savedToken) {
      token.value = savedToken
    }
    if (savedUser) {
      try {
        user.value = JSON.parse(savedUser)
      } catch {
        localStorage.removeItem('user')
      }
    }
  }

  async function login(username: string, password: string) {
    const res = await authAPI.login({ username, password })
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    return res
  }

  async function register(data: { username: string; email: string; password: string; role?: string }) {
    const res = await authAPI.register(data)
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    return res
  }

  async function fetchMe() {
    try {
      const me = await authAPI.getMe()
      user.value = me
      localStorage.setItem('user', JSON.stringify(me))
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
  }

  return {
    user,
    token,
    isLoggedIn,
    isTeacher,
    isStudent,
    initialize,
    login,
    register,
    fetchMe,
    logout,
  }
})
