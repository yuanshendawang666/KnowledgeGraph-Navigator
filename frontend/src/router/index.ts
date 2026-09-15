import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    children: [
      {
        path: '',
        name: 'CourseList',
        component: () => import('@/views/CourseListView.vue'),
        meta: { title: '课程列表' },
      },
      {
        path: 'course/:id',
        name: 'CourseDetail',
        component: () => import('@/views/CourseDetailView.vue'),
        meta: { title: '课程详情' },
      },
      {
        path: 'course/:id/knowledge',
        name: 'KnowledgePoints',
        component: () => import('@/views/KnowledgePointsView.vue'),
        meta: { title: '知识点列表' },
      },
      {
        path: 'course/:id/knowledge/:kpId',
        name: 'KnowledgeDetail',
        component: () => import('@/views/KnowledgeDetailView.vue'),
        meta: { title: '知识点详情' },
      },
      {
        path: 'course/:id/practice',
        name: 'Practice',
        component: () => import('@/views/PracticeView.vue'),
        meta: { title: '智能练习' },
      },
      {
        path: 'course/:id/quiz-manage',
        name: 'TeacherQuiz',
        component: () => import('@/views/TeacherQuizView.vue'),
        meta: { title: '题库管理' },
      },
      {
        path: 'progress/:id',
        name: 'LearningProgress',
        component: () => import('@/views/LearningProgressView.vue'),
        meta: { title: '学习进度' },
      },
      {
        path: 'qa',
        name: 'QA',
        component: () => import('@/views/QAView.vue'),
        meta: { title: '智能问答' },
      },
      {
        path: 'classroom',
        name: 'Classroom',
        component: () => import('@/views/ClassroomView.vue'),
        meta: { title: '班级管理' },
      },
      {
        path: 'notes',
        name: 'Notes',
        component: () => import('@/views/NotesView.vue'),
        meta: { title: '学习笔记' },
      },
      {
        path: 'practice',
        name: 'PracticeHome',
        component: () => import('@/views/TeacherQuizView.vue'),
        meta: { title: 'AI 出题' },
      },
      {
        path: 'practice-student',
        name: 'StudentPracticeHome',
        component: () => import('@/views/PracticeHomeView.vue'),
        meta: { title: '在线练习' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

// 路由守卫 — JWT 鉴权
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.guest) {
    // 已登录用户访问登录/注册页 → 重定向到首页
    if (token) {
      return next('/')
    }
    return next()
  }

  // 未登录用户 → 重定向到登录页
  if (!token) {
    return next('/login')
  }

  next()
})

export default router
