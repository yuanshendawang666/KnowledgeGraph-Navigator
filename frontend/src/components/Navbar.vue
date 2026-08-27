<template>
  <header class="navbar">
    <div class="navbar-left">
      <button class="menu-toggle" @click="$emit('toggleSidebar')" aria-label="切换侧边栏">
        <el-icon :size="20"><Fold /></el-icon>
      </button>
      <span class="navbar-title">{{ pageTitle }}</span>
    </div>
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
.navbar { background:linear-gradient(90deg,#ffffff 0%,#f7fbff 58%,#fffaf2 100%); border-bottom:1px solid #dfe8e1; box-shadow:0 1px 0 rgba(15,23,42,.02); }
.menu-toggle { background:linear-gradient(135deg,#eaf2ff,#eafbf0); color:#2563eb; }
.menu-toggle:hover { background:#ecfdf3; color:#166534; }
.navbar-title { color:#243b53; font-weight:700; }
</style>
