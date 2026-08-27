<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': collapsed }">
    <Sidebar :collapsed="collapsed" @toggle="collapsed = !collapsed" />
    <div class="app-main">
      <Navbar @toggle-sidebar="collapsed = !collapsed" />
      <main class="app-content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import Sidebar from './Sidebar.vue'
import Navbar from './Navbar.vue'

const auth = useAuthStore()
const collapsed = ref(false)

onMounted(() => {
  auth.fetchMe()
})
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--color-surface-overlay);
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  transition: margin-left var(--duration-slow) var(--ease-out);
}

.app-content {
  flex: 1;
  padding: var(--space-6);
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
  background: transparent;
}

@media (max-width: 760px) {
  .app-content { padding: 18px 14px; }
}
</style>
