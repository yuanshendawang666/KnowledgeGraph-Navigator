<template>
  <router-view :style="route.meta.guest ? {} : null" />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

onMounted(() => {
  auth.initialize()

  // 移除页面加载的过渡阻止
  requestAnimationFrame(() => {
    document.body.classList.remove('no-transition')
  })
})
</script>
