<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- 品牌区 — 与顶栏搭配的渐变 -->
    <div class="sidebar-brand" @click="goHome">
      <img src="/logo.png" alt="知谱智航" class="brand-logo" />
      <transition name="fade">
        <span v-if="!collapsed" class="brand-text">知谱智航</span>
      </transition>
    </div>

    <!-- 导航菜单 -->
    <nav class="sidebar-nav">
      <router-link to="/" class="nav-item nav-courses" :class="{ active: isActive('/') }">
        <span class="nav-icon courses-icon">
          <el-icon :size="18"><Reading /></el-icon>
        </span>
        <span v-if="!collapsed" class="nav-label">课程列表</span>
      </router-link>

      <router-link to="/qa" class="nav-item nav-qa" :class="{ active: isActive('/qa') }">
        <span class="nav-icon qa-icon">
          <el-icon :size="18"><ChatDotRound /></el-icon>
        </span>
        <span v-if="!collapsed" class="nav-label">智能问答</span>
      </router-link>

      <router-link to="/notes" class="nav-item nav-notes" :class="{ active: isActive('/notes') }">
        <span class="nav-icon notes-icon">
          <el-icon :size="18"><Notebook /></el-icon>
        </span>
        <span v-if="!collapsed" class="nav-label">学习笔记</span>
      </router-link>

      <router-link v-if="auth.isTeacher" to="/practice" class="nav-item nav-practice" :class="{ active: isActive('/practice') }">
        <span class="nav-icon practice-icon"><el-icon :size="18"><EditPen /></el-icon></span>
        <span v-if="!collapsed" class="nav-label">AI 出题</span>
      </router-link>
      <router-link v-else to="/practice-student" class="nav-item nav-practice" :class="{ active: isActive('/practice-student') }">
        <span class="nav-icon practice-icon"><el-icon :size="18"><EditPen /></el-icon></span>
        <span v-if="!collapsed" class="nav-label">在线练习</span>
      </router-link>

      <router-link to="/classroom" class="nav-item nav-classroom" :class="{ active: isActive('/classroom') }">
        <span class="nav-icon classroom-icon">
          <el-icon :size="18"><School /></el-icon>
        </span>
        <span v-if="!collapsed" class="nav-label">班级管理</span>
      </router-link>
    </nav>

    <!-- 用户信息区 — 展开时显示详细信息 -->
    <div class="sidebar-user">
      <!-- 展开状态：完整用户卡片 -->
      <div class="user-card" v-if="!collapsed">
        <div class="user-card-top">
          <span class="user-avatar" :class="auth.isTeacher ? 'avatar-teacher' : 'avatar-student'">
            {{ auth.user?.username?.charAt(0)?.toUpperCase() }}
          </span>
          <div class="user-info">
            <span class="user-name">{{ auth.user?.username }}</span>
            <span class="user-role" :class="auth.isTeacher ? 'role-teacher' : 'role-student'">
              {{ auth.isTeacher ? '教师' : '学生' }}
            </span>
          </div>
          <el-popconfirm title="确定退出登录？" @confirm="auth.logout()">
            <template #reference>
              <button class="user-logout" title="退出登录">
                <el-icon :size="14"><SwitchButton /></el-icon>
              </button>
            </template>
          </el-popconfirm>
        </div>

        <div class="user-card-details">
          <div class="detail-row">
            <el-icon :size="13"><Message /></el-icon>
            <span class="detail-text">{{ auth.user?.email || '未设置邮箱' }}</span>
          </div>
          <div class="detail-row">
            <el-icon :size="13"><Calendar /></el-icon>
            <span class="detail-text">加入于 {{ formattedDate }}</span>
          </div>
        </div>

        <button class="edit-profile-btn" @click="showEditDialog = true">
          <el-icon :size="13"><Edit /></el-icon>
          编辑资料
        </button>
      </div>

      <!-- 折叠状态：迷你头像 -->
      <button
        v-else
        class="user-avatar-mini"
        :class="auth.isTeacher ? 'avatar-teacher' : 'avatar-student'"
        @click="auth.logout()"
        :title="auth.user?.username"
      >
        {{ auth.user?.username?.charAt(0)?.toUpperCase() }}
      </button>
    </div>

    <!-- 折叠按钮 -->
    <div class="sidebar-footer">
      <button class="collapse-btn" @click="$emit('toggle')" :aria-label="collapsed ? '展开侧边栏' : '折叠侧边栏'">
        <el-icon :size="16">
          <DArrowLeft v-if="!collapsed" />
          <DArrowRight v-else />
        </el-icon>
      </button>
    </div>

    <!-- 编辑资料对话框 -->
    <Teleport to="body">
      <el-dialog v-model="showEditDialog" title="编辑个人资料" width="420px" destroy-on-close>
        <el-form :model="editForm" label-position="top">
          <el-form-item label="用户名">
            <el-input v-model="editForm.username" placeholder="用户名" />
          </el-form-item>
          <el-form-item label="邮箱">
            <el-input v-model="editForm.email" placeholder="邮箱地址" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showEditDialog = false">取消</el-button>
          <el-button type="primary" @click="saveProfile">保存</el-button>
        </template>
      </el-dialog>
    </Teleport>
  </aside>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import {
  Reading, ChatDotRound, DArrowLeft, DArrowRight,
  SwitchButton, Message, Calendar, Edit, EditPen, Notebook, School,
} from '@element-plus/icons-vue'

defineProps<{ collapsed: boolean }>()
defineEmits<{ toggle: [] }>()

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const showEditDialog = ref(false)

const editForm = reactive({
  username: auth.user?.username || '',
  email: auth.user?.email || '',
})

const formattedDate = computed(() => {
  const d = auth.user?.created_at ? new Date(auth.user.created_at) : new Date()
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
})

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function goHome() {
  router.push('/')
}

function saveProfile() {
  ElMessage.success('资料已更新（演示）')
  showEditDialog.value = false
}
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: 230px;
  min-width: 0;
  background: linear-gradient(180deg, #e4eeff 0%, #f2f7fd 50%, #fdf6e8 100%);
  border-right: 1px solid #ccdaf0;
  transition: width var(--duration-slow) var(--ease-out);
  flex-shrink: 0;
  position: sticky;
  top: 0;
  height: 100vh;
  z-index: 100;
}

.sidebar.collapsed {
  width: 64px;
}

/* 品牌区 — 和顶栏同色系 */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 56px;
  padding: 0 var(--space-4);
  cursor: pointer;
  background: linear-gradient(135deg, #f0f5fe 0%, #eff7f2 40%, #faf3e4 100%);
  border-bottom: 1px solid #d4e0f2;
  flex-shrink: 0;
  overflow: hidden;
}

.brand-logo {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  object-fit: contain;
}

.brand-text {
  font-size: var(--font-size-md);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #1e40af;
  white-space: nowrap;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  padding: var(--space-4) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: linear-gradient(180deg, #dce8fc 0%, #eef4fa 40%, #f5f9ee 70%, #fcf6e8 100%);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  height: 44px;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: all var(--duration-fast) var(--ease-out);
  overflow: hidden;
  white-space: nowrap;
  border-left: 3px solid transparent;
  background: rgba(255,255,255,0.6);
}

.nav-item:hover { border-left-color: #93c5fd; background: rgba(255,255,255,0.95); }

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  flex-shrink: 0;
  transition: all var(--duration-fast) var(--ease-out);
}

/* 课程列表 — 蓝色系 */
.courses-icon { background: #bfdbfe; color: #1d4ed8; box-shadow: 0 1px 2px rgba(37,99,235,0.2); }
.nav-courses { background: #eff6ff; }
.nav-courses:hover { background: #dbeafe; color: #1e40af; border-left-color: #3b82f6; }
.nav-courses:hover .courses-icon { background: #93c5fd; color: #1e40af; }
.nav-courses.active { background: #bfdbfe; color: #1e3a8a; font-weight: 600; border-left-color: #2563eb; }
.nav-courses.active .courses-icon { background: #60a5fa; color: #1e3a8a; }

/* 智能问答 — 暖橙色系 */
.qa-icon { background: #fed7aa; color: #9a3412; box-shadow: 0 1px 2px rgba(234,88,12,0.2); }
.nav-qa { background: #fff7ed; }
.nav-qa:hover { background: #ffedd5; color: #9a3412; border-left-color: #f97316; }
.nav-qa:hover .qa-icon { background: #fdba74; color: #9a3412; }
.nav-qa.active { background: #fed7aa; color: #7c2d12; font-weight: 600; border-left-color: #ea580c; }
.nav-qa.active .qa-icon { background: #fb923c; color: #7c2d12; }

/* 学习笔记 — 绿色系 */
.notes-icon { background: #bbf7d0; color: #15803d; box-shadow: 0 1px 2px rgba(22,163,74,0.2); }
.nav-notes { background: #f0fdf4; }
.nav-notes:hover { background: #dcfce7; color: #166534; border-left-color: #22c55e; }
.nav-notes:hover .notes-icon { background: #86efac; color: #166534; }
.nav-notes.active { background: #bbf7d0; color: #14532d; font-weight: 600; border-left-color: #16a34a; }
.nav-notes.active .notes-icon { background: #4ade80; color: #14532d; }

/* 班级管理 — 紫色系 */
.classroom-icon { background: #ddd6fe; color: #6d28d9; box-shadow: 0 1px 2px rgba(124,58,237,0.2); }
.nav-classroom { background: #f5f3ff; }
.nav-classroom:hover { background: #ede9fe; color: #5b21b6; border-left-color: #a78bfa; }
.nav-classroom:hover .classroom-icon { background: #c4b5fd; color: #5b21b6; }
.nav-classroom.active { background: #ddd6fe; color: #4c1d95; font-weight: 600; border-left-color: #7c3aed; }
.nav-classroom.active .classroom-icon { background: #a78bfa; color: #4c1d95; }

.nav-label {
  opacity: 1;
  transition: opacity var(--duration-fast) var(--ease-out);
}
.collapsed .nav-label { opacity: 0; }

/* 用户区 */
.sidebar-user {
  padding: var(--space-3);
  border-top: 1px solid #e0f2fe;
}

.user-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  border: 1px solid #e2e8f0;
}

.user-card-top {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.user-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-md);
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}
.avatar-teacher { background: linear-gradient(135deg, #f59e0b, #d97706); }
.avatar-student { background: linear-gradient(135deg, #3b82f6, #2563eb); }

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.user-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-role {
  font-size: var(--font-size-xs);
  font-weight: 600;
}
.role-teacher { color: #d97706; }
.role-student { color: #2563eb; }

.user-logout {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}
.user-logout:hover { background: #fef2f2; color: #ef4444; }

/* 用户详情行 */
.user-card-details {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid #e2e8f0;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-text-tertiary);
}
.detail-text {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edit-profile-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) 0;
  border: 1px dashed #cbd5e1;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-tertiary);
  font-family: inherit;
  font-size: var(--font-size-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.edit-profile-btn:hover {
  border-color: #3b82f6;
  color: #3b82f6;
  background: #eff6ff;
}

/* 迷你头像 */
.user-avatar-mini {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  margin: 0 auto;
  border: none;
  border-radius: var(--radius-full);
  font-family: inherit;
  font-size: var(--font-size-sm);
  font-weight: 700;
  color: white;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.user-avatar-mini:hover { transform: scale(1.05); }

/* 折叠按钮 */
.sidebar-footer {
  padding: var(--space-3);
  border-top: 1px solid #e0f2fe;
}
.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 34px;
  border: none;
  border-radius: var(--radius-md);
  background: rgba(59, 130, 246, 0.04);
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.collapse-btn:hover {
  background: rgba(59, 130, 246, 0.1);
  color: var(--color-brand-500);
}

.fade-enter-active, .fade-leave-active { transition: opacity var(--duration-fast) var(--ease-out); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
/* 统一壳层：导航承担结构，不承担装饰拼色 */
.sidebar { background:linear-gradient(180deg,#f7fbff 0%,#f9fbf7 56%,#fff9ef 100%); border-right:1px solid #dfe8e1; }
.sidebar-brand { background:linear-gradient(135deg,#f0f6ff,#f1fbf3 58%,#fff8ec); border-bottom:1px solid #e3e9e3; }
.brand-text { color:#2454a6; }
.sidebar-nav { background:linear-gradient(180deg,rgba(226,237,255,.72),rgba(238,249,240,.62) 62%,rgba(255,247,232,.6)); padding:18px 12px; gap:8px; }
.nav-item,.nav-courses,.nav-qa,.nav-notes,.nav-classroom { background:transparent; border-left:3px solid transparent; color:#64748b; }
.nav-item:hover { background:#fff; border-left-color:#bbf7d0; color:#334155; }
.nav-item.active { box-shadow:0 2px 8px rgba(15,23,42,.05); }
.nav-courses.active { background:#eff6ff; border-left-color:#3b82f6; color:#1d4ed8; }
.nav-qa.active { background:#fff7ed; border-left-color:#f59e0b; color:#c2410c; }
.nav-notes.active { background:#ecfdf3; border-left-color:#22c55e; color:#166534; }
.nav-classroom.active { background:#f5f3ff; border-left-color:#8b5cf6; color:#6d28d9; }
.nav-icon,.courses-icon,.qa-icon,.notes-icon,.classroom-icon { background:#fff; color:#64748b; box-shadow:none; }
.nav-courses.active .nav-icon { background:#dbeafe; color:#2563eb; }
.nav-qa.active .nav-icon { background:#fed7aa; color:#ea580c; }
.nav-notes.active .nav-icon { background:#dcfce7; color:#15803d; }
.nav-classroom.active .nav-icon { background:#ede9fe; color:#7c3aed; }
.nav-courses .nav-icon { background:#eff6ff; color:#2563eb; }
.nav-qa .nav-icon { background:#fff7ed; color:#ea580c; }
.nav-notes .nav-icon { background:#ecfdf3; color:#16a34a; }
.nav-classroom .nav-icon { background:#f5f3ff; color:#7c3aed; }
.nav-courses:hover { background:#f8fbff; }
.nav-qa:hover { background:#fffaf5; }
.nav-notes:hover { background:#f5fcf7; }
.nav-classroom:hover { background:#faf9ff; }
.nav-courses { background:#f5f9ff; }
.nav-qa { background:#fffaf4; }
.nav-notes { background:#f4fbf6; }
.nav-classroom { background:#faf8ff; }
.sidebar-user { background:#fbfcfa; border-top:1px solid #edf0eb; }
.user-card { background:#fff; border-color:#e4e8e2; box-shadow:0 4px 14px rgba(15,23,42,.04); }
.sidebar-footer { background:#fbfcfa; border-top:1px solid #edf0eb; }
.collapse-btn { background:#f1f4ef; color:#94a3b8; }
.collapse-btn:hover { background:#ecfdf3; color:#15803d; }
.nav-practice { background:#fff7fb; }
.practice-icon { background:#fce7f3 !important; color:#db2777 !important; }
.nav-practice:hover { background:#fdf2f8; color:#be185d; border-left-color:#ec4899; }
.nav-practice.active { background:#fce7f3; color:#9d174d; border-left-color:#db2777; font-weight:600; }
.nav-practice.active .practice-icon { background:#f9a8d4 !important; color:#9d174d !important; }
.sidebar { background:#f7fbff; }
.sidebar-brand { background:#f7fbff; }
.sidebar-nav { background:#f7fbff; }
.sidebar-user { background:#f7fbff; }
.sidebar-footer { background:#f7fbff; }
.nav-courses { background:#dbeafe !important; color:#1e3a8a !important; }
.nav-courses .nav-icon { background:#93c5fd !important; color:#1e40af !important; }
.nav-qa { background:#ffedd5 !important; color:#9a3412 !important; }
.nav-qa .nav-icon { background:#fdba74 !important; color:#9a3412 !important; }
.nav-notes { background:#dcfce7 !important; color:#166534 !important; }
.nav-notes .nav-icon { background:#86efac !important; color:#166534 !important; }
.nav-practice { background:#fce7f3 !important; color:#9d174d !important; }
.nav-practice .nav-icon { background:#f9a8d4 !important; color:#9d174d !important; }
.nav-classroom { background:#ede9fe !important; color:#5b21b6 !important; }
.nav-classroom .nav-icon { background:#c4b5fd !important; color:#5b21b6 !important; }
.nav-item.active { box-shadow:0 5px 14px rgba(15,23,42,.12); font-weight:700; }
.nav-courses.active { border-left-color:#1d4ed8; background:#bfdbfe !important; }
.nav-qa.active { border-left-color:#c2410c; background:#fed7aa !important; }
.nav-notes.active { border-left-color:#15803d; background:#bbf7d0 !important; }
.nav-practice.active { border-left-color:#be185d; background:#f9a8d4 !important; }
.nav-classroom.active { border-left-color:#6d28d9; background:#ddd6fe !important; }
.sidebar.collapsed .sidebar-nav { padding-left:10px; padding-right:10px; align-items:center; }
.sidebar.collapsed .nav-item { width:44px; height:48px; padding:0; justify-content:center; gap:0; border-left:0; border-radius:14px; }
.sidebar.collapsed .nav-item.active { box-shadow:0 4px 12px rgba(15,23,42,.14); }
.sidebar.collapsed .nav-icon { width:36px; height:36px; }
</style>
