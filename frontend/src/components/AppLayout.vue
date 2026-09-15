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
    <button v-if="auth.isStudent" class="preference-entry" type="button" @click="showPreferences = true">
      <span>✦</span> 调整推荐偏好
    </button>
    <PreferenceOnboarding v-model="showPreferences" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import Sidebar from './Sidebar.vue'
import Navbar from './Navbar.vue'
import PreferenceOnboarding from './PreferenceOnboarding.vue'

const auth = useAuthStore()
const collapsed = ref(false)
const showPreferences = ref(false)

onMounted(async () => {
  await auth.fetchMe()
  if (auth.isStudent && !auth.user?.onboarding_completed) showPreferences.value = true
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
.preference-entry{position:fixed;right:24px;bottom:24px;z-index:60;display:flex;align-items:center;gap:8px;padding:11px 16px;border:1px solid #cce8e2;border-radius:999px;background:rgba(255,255,255,.94);color:#08776c;font-weight:700;box-shadow:0 10px 28px rgba(20,72,91,.14);backdrop-filter:blur(10px);cursor:pointer;transition:.2s}.preference-entry:hover{transform:translateY(-2px);border-color:#6bcbbb;box-shadow:0 14px 32px rgba(20,72,91,.2)}.preference-entry span{color:#0e9d8b}

@media (max-width: 760px) {
  .app-content { padding: 18px 14px; }
}
</style>
