import { ref, watchEffect } from 'vue'

const isDark = ref(false)

export function useDark() {
  // 初始化 — 读取 localStorage 或系统偏好
  const saved = localStorage.getItem('darkMode')
  if (saved !== null) {
    isDark.value = saved === 'true'
  } else {
    isDark.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  }

  watchEffect(() => {
    document.documentElement.classList.toggle('dark', isDark.value)
    localStorage.setItem('darkMode', String(isDark.value))
  })

  function toggleDark() {
    isDark.value = !isDark.value
  }

  return { isDark, toggleDark }
}
