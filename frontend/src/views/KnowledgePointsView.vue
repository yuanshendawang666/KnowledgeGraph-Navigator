<template>
  <div class="kp-page">
    <button class="back-link" @click="$router.push(`/course/${courseId}`)">
      <el-icon :size="16"><ArrowLeft /></el-icon>
      返回课程详情
    </button>

    <header class="kp-header">
      <h1 class="page-title">课程知识点</h1>
      <p class="page-subtitle">{{ courseTitle }} &mdash; 共 {{ filteredPoints.length }} 个知识点</p>
    </header>

    <!-- 搜索 + 筛选 -->
    <div class="kp-toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索知识点名称或简介..."
        clearable
        class="kp-search"
        size="default"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-radio-group v-model="filterType" size="default">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="leaf">知识点</el-radio-button>
        <el-radio-button value="module">模块</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 知识点列表 -->
    <div class="kp-grid" v-loading="loading">
      <article
        v-for="kp in filteredPoints"
        :key="kp.id"
        class="kp-card"
        @click="goDetail(kp)"
      >
        <div class="kp-card-head">
          <h3 class="kp-card-name">{{ kp.name }}</h3>
          <el-tag :type="typeTag(kp)" size="small">{{ typeLabel(kp) }}</el-tag>
        </div>
        <p class="kp-card-desc">{{ kp.description || '暂无简介' }}</p>
        <div class="kp-card-foot">
          <span v-if="statusOf(kp.id)" class="kp-status" :class="statusOf(kp.id)">
            {{ statusText(statusOf(kp.id)) }}
          </span>
          <el-icon class="kp-arrow" :size="14"><ArrowRight /></el-icon>
        </div>
      </article>

      <div v-if="!loading && !filteredPoints.length" class="empty-state">
        <p>没有匹配的知识点</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Search, ArrowRight } from '@element-plus/icons-vue'
import { coursesAPI, type KnowledgePointItem } from '@/api/courses'
import { learningAPI } from '@/api/learning'

const route = useRoute()
const router = useRouter()
const courseId = Number(route.params.id)
const courseTitle = ref('')
const knowledgePoints = ref<KnowledgePointItem[]>([])
const statusMap = ref<Record<number, string>>({})
const loading = ref(false)
const keyword = ref('')
const filterType = ref<'all' | 'leaf' | 'module'>('all')

const filteredPoints = computed(() => {
  let list = knowledgePoints.value
  if (filterType.value === 'leaf') {
    list = list.filter(k => !k.is_module)
  } else if (filterType.value === 'module') {
    list = list.filter(k => k.is_module)
  }
  const kw = keyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter(k =>
      k.name.toLowerCase().includes(kw) ||
      (k.description || '').toLowerCase().includes(kw)
    )
  }
  return list
})

function typeLabel(kp: KnowledgePointItem): string {
  if (kp.level === 0) return '模块'
  if (kp.level === 1) return '子模块'
  return '知识点'
}

function typeTag(kp: KnowledgePointItem): string {
  if (kp.level === 0) return 'primary'
  if (kp.level === 1) return 'warning'
  return 'info'
}

function statusOf(id: number): string | undefined {
  return statusMap.value[id]
}

function statusText(s?: string): string {
  const map: Record<string, string> = { mastered: '已掌握', in_progress: '学习中', not_started: '未开始' }
  return map[s || ''] || s || ''
}

function goDetail(kp: KnowledgePointItem) {
  router.push(`/course/${courseId}/knowledge/${kp.id}`)
}

onMounted(async () => {
  loading.value = true
  try {
    const course = await coursesAPI.getDetail(courseId)
    courseTitle.value = course.title
    knowledgePoints.value = course.knowledge_points || []

    // 学习进度（掌握状态）
    try {
      const progress = await learningAPI.getProgress(courseId)
      const map: Record<number, string> = {}
      for (const r of (progress as any).records || []) {
        map[r.knowledge_point_id] = r.status
      }
      statusMap.value = map
    } catch { /* 进度加载失败不影响列表 */ }
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.kp-page { max-width: 900px; margin: 0 auto; }

.back-link {
  display: inline-flex; align-items: center; gap: var(--space-2);
  border: none; background: none; color: var(--color-text-tertiary);
  font-family: inherit; font-size: var(--font-size-sm); cursor: pointer;
  padding: 0; margin-bottom: var(--space-4); transition: color var(--duration-fast);
}
.back-link:hover { color: var(--color-text-primary); }

.kp-header { margin-bottom: var(--space-6); }
.page-title { font-size: var(--font-size-3xl); font-weight: 700; margin: 0; color: var(--color-text-primary); }
.page-subtitle { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin: var(--space-2) 0 0; }

.kp-toolbar {
  display: flex; align-items: center; gap: var(--space-4);
  margin-bottom: var(--space-6); flex-wrap: wrap;
}
.kp-search { max-width: 340px; }

.kp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: var(--space-4); }

.kp-card {
  display: flex; flex-direction: column; gap: var(--space-3);
  padding: var(--space-5);
  background: var(--color-surface-default); border: 1.5px solid #bfdbfe;
  border-radius: var(--radius-lg); cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}
.kp-card:hover { border-color: #93c5fd; box-shadow: var(--shadow-md); transform: translateY(-2px); }

.kp-card-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.kp-card-name { font-size: var(--font-size-md); font-weight: 600; color: var(--color-text-primary); margin: 0; flex: 1; min-width: 0; }
.kp-card-desc {
  font-size: var(--font-size-sm); color: var(--color-text-secondary);
  margin: 0; line-height: var(--line-height-relaxed);
  overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}

.kp-card-foot { display: flex; align-items: center; justify-content: space-between; }
.kp-status { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-full); }
.kp-status.mastered { background: #dcfce7; color: #15803d; }
.kp-status.in_progress { background: #fef9c3; color: #a16207; }
.kp-status.not_started { background: #f1f5f9; color: #64748b; }
.kp-arrow { color: var(--color-text-placeholder); }

.empty-state { grid-column: 1 / -1; text-align: center; padding: var(--space-16); color: var(--color-text-tertiary); }
</style>
