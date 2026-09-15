<template>
  <header class="navbar">
    <div class="navbar-left">
      <button class="menu-toggle" @click="$emit('toggleSidebar')" aria-label="切换侧边栏">
        <el-icon :size="20"><Fold /></el-icon>
      </button>
      <span class="navbar-title">{{ pageTitle }}</span>
    </div>
    <div class="navbar-context"><span class="context-dot"></span>知谱智航 · 学习工作台</div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Fold } from '@element-plus/icons-vue'

defineEmits<{ toggleSidebar: [] }>()

const route = useRoute()

const pageTitle = computed(() => {
  const meta = route.meta as { title?: string }
  return meta.title || '知谱智航'
})
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 var(--space-6);
  background: linear-gradient(135deg, #f2f6fc 0%, #f4faf6 40%, #fcf9f2 100%);
  border-bottom: 1px solid #d8e4f0;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 50;
}

.navbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.menu-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: var(--radius-md);
  background: rgba(59, 130, 246, 0.08);
  color: var(--color-brand-500);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.menu-toggle:hover {
  background: rgba(59, 130, 246, 0.16);
  color: var(--color-brand-600);
}

.navbar-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: 0.02em;
}
.navbar { height:64px; background:linear-gradient(90deg,var(--module-soft),#fff 72%); border-bottom:1px solid #e1e7f0; box-shadow:0 1px 0 rgba(15,23,42,.02); }
.menu-toggle { background:var(--module-soft); color:var(--module-color); border:1px solid var(--module-line); }
.menu-toggle:hover { background:var(--module-line); color:var(--module-color); }
.navbar-context { display:flex; align-items:center; gap:8px; color:#64748b; font-size:12px; }
.context-dot { width:8px; height:8px; background:var(--module-color); border-radius:50%; }
@media(max-width:600px) { .navbar-context { display:none; } }
.navbar-title { color:#243b53; font-weight:700; }
</style>
