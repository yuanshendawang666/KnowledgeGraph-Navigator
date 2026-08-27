<template>
  <div class="progress-view">
    <!-- 返回 -->
    <button class="back-link" @click="$router.push(`/course/${courseId}`)">
      <el-icon :size="16"><ArrowLeft /></el-icon>
      返回课程详情
    </button>

    <!-- 课程信息 -->
    <header class="progress-header">
      <h1 class="page-title">学习进度</h1>
      <p class="page-subtitle">课程 ID: {{ courseId }}</p>
    </header>

    <!-- 统计卡片 -->
    <div class="stats-row" v-if="stats">
      <div class="stat-card" v-for="s in statItems" :key="s.key" :class="s.key">
        <span class="stat-value" :style="{ color: s.color }">{{ s.value }}</span>
        <span class="stat-label">{{ s.label }}</span>
      </div>
    </div>

    <!-- 进度条 -->
    <div class="progress-bar-wrap" v-if="stats">
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: stats.progress_percentage + '%' }"
        ></div>
      </div>
      <span class="progress-text">{{ Math.round(stats.progress_percentage) }}% 已掌握</span>
      <el-button type="primary" size="small" @click="goAdaptivePractice">
        智能练习
      </el-button>
    </div>

    <!-- Tab -->
    <el-tabs v-model="activeTab" class="progress-tabs" @tab-change="onTabChange">
      <el-tab-pane label="全部知识点" name="all">
        <div class="kp-table-wrap">
          <el-table :data="records" stripe style="width: 100%" v-loading="loading" empty-text="暂无学习记录">
            <el-table-column prop="knowledge_point_name" label="知识点" min-width="180">
              <template #default="{ row }">
                <span class="kp-cell-name">{{ row.knowledge_point_name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="掌握状态" width="160">
              <template #default="{ row }">
                <el-select
                  :model-value="row.status"
                  size="small"
                  @change="(v: KnowledgeStatus) => updateStatus(row, v)"
                  style="width: 130px"
                >
                  <el-option value="not_started" label="未开始" />
                  <el-option value="in_progress" label="学习中" />
                  <el-option value="mastered" label="已掌握" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column prop="mastery_level" label="掌握程度" width="140">
              <template #default="{ row }">
                <el-progress
                  :percentage="(row.mastery_level || 0) * 100"
                  :stroke-width="6"
                  :show-text="false"
                  :color="masteryColor(row.mastery_level)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="primary"
                  link
                  @click="goKpPractice(row.knowledge_point_id)"
                >练习</el-button>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="180">
              <template #default="{ row }">
                <span class="text-tertiary" style="font-size: var(--font-size-xs)">
                  {{ formatDate(row.updated_at) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="学习推荐" name="recommend">
        <div v-if="recommendLoading" class="loading-state">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <span>正在分析学习路径…</span>
        </div>
        <div v-else-if="recommendations.length" class="recommend-list">
          <div v-for="(item, idx) in recommendations" :key="item.neo4j_node_id" class="recommend-item">
            <div class="recommend-rank">{{ idx + 1 }}</div>
            <div class="recommend-body">
              <span class="recommend-name">{{ item.name }}</span>
              <span class="recommend-desc" v-if="item.description">{{ item.description }}</span>
              <span class="recommend-reason" v-if="item.reason">
                <el-icon :size="12"><InfoFilled /></el-icon>
                {{ item.reason }}
              </span>
            </div>
            <el-tag :type="statusTagType(item.status)" size="small" round>
              {{ statusLabel(item.status) }}
            </el-tag>
            <el-button
              size="small"
              type="primary"
              @click="goKpPractice(item.knowledge_point_id)"
            >开始练习</el-button>
          </div>
        </div>
        <div v-else class="inline-empty">
          <p>暂无推荐数据，请确保课程包含知识图谱</p>
          <el-button
            size="small"
            @click="fetchRecommend"
            style="margin-top: var(--space-3)"
          >获取推荐</el-button>
        </div>
      </el-tab-pane>

      <el-tab-pane label="学习方法" name="methods">
        <div v-if="methodsLoading" class="loading-state">
          <el-icon class="is-loading" :size="24"><Loading /></el-icon>
          <span>正在生成学习方法建议…</span>
        </div>
        <div v-else-if="methodsData" class="methods-wrap">
          <p class="methods-summary">{{ methodsData.summary }}</p>
          <div v-for="(m, i) in methodsData.methods" :key="i" class="method-item">
            <div class="method-head">
              <span class="method-rank">{{ i + 1 }}</span>
              <span class="method-title">{{ m.title }}</span>
            </div>
            <p class="method-desc">{{ m.description }}</p>
            <p class="method-reason">
              <el-icon :size="12"><InfoFilled /></el-icon> {{ m.reason }}
            </p>
          </div>
          <div class="method-refresh">
            <el-button size="small" @click="fetchStudyMethods">重新生成</el-button>
          </div>
        </div>
        <div v-else class="inline-empty">
          <p>AI 将根据你的学习进度和薄弱点，推荐具体的学习方法</p>
          <el-button
            size="small"
            type="primary"
            @click="fetchStudyMethods"
            style="margin-top: var(--space-3)"
          >生成学习方法</el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loading, InfoFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { learningAPI, type ProgressRecord, type CourseStats, type KnowledgeStatus } from '@/api/learning'

const route = useRoute()
const router = useRouter()
const courseId = computed(() => Number(route.params.id))
const activeTab = ref('all')

const records = ref<ProgressRecord[]>([])
const stats = ref<CourseStats | null>(null)
const recommendations = ref<Array<{
  neo4j_node_id: string
  knowledge_point_id: number
  name: string
  description: string
  reason: string
  status: KnowledgeStatus
}>>([])
const loading = ref(false)
const recommendLoading = ref(false)
const methodsLoading = ref(false)
const methodsData = ref<{ summary: string; methods: Array<{ title: string; description: string; reason: string }> } | null>(null)

const statItems = computed(() => {
  if (!stats.value) return []
  return [
    { key: 'total', value: stats.value.total, label: '总知识点', color: 'var(--color-brand-600)' },
    { key: 'mastered', value: stats.value.mastered, label: '已掌握', color: 'var(--color-success)' },
    { key: 'in_progress', value: stats.value.in_progress, label: '学习中', color: 'var(--color-warning)' },
    { key: 'not_started', value: stats.value.not_started, label: '未开始', color: 'var(--color-text-tertiary)' },
  ]
})

function masteryColor(level: number): string {
  if (level >= 0.8) return 'var(--color-success)'
  if (level >= 0.4) return 'var(--color-warning)'
  return 'var(--color-text-placeholder)'
}

function statusTagType(status: KnowledgeStatus): 'info' | 'warning' | 'success' {
  switch (status) {
    case 'mastered': return 'success'
    case 'in_progress': return 'warning'
    default: return 'info'
  }
}

function statusLabel(status: KnowledgeStatus): string {
  switch (status) {
    case 'not_started': return '未开始'
    case 'in_progress': return '学习中'
    case 'mastered': return '已掌握'
    default: return status
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function fetchProgress() {
  loading.value = true
  try {
    const res = await learningAPI.getProgress(courseId.value) as any
    records.value = res.records || []
    stats.value = {
      total: res.total_points ?? res.stats?.total ?? 0,
      mastered: res.mastered_count ?? res.stats?.mastered ?? 0,
      in_progress: res.in_progress_count ?? res.stats?.in_progress ?? 0,
      not_started: res.not_started_count ?? res.stats?.not_started ?? 0,
      progress_percentage: res.progress_percentage ?? res.stats?.progress_percentage ?? 0,
    }
  } catch {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

async function fetchRecommend() {
  recommendLoading.value = true
  try {
    const res = await learningAPI.getRecommend(courseId.value) as any
    const ready = res.ready_to_learn || res.recommended_next || []
    const kpIdMap = new Map(
      records.value.map(r => [r.neo4j_node_id, r.knowledge_point_id]),
    )
    recommendations.value = ready.map((kp: any) => ({
      neo4j_node_id: kp.id,
      knowledge_point_id: kpIdMap.get(kp.id) || 0,
      name: kp.label || kp.name,
      description: kp.description || '',
      reason: '先修条件已满足，推荐优先学习',
      status: 'not_started' as KnowledgeStatus,
    }))
  } catch {
    // 错误已处理
  } finally {
    recommendLoading.value = false
  }
}

async function fetchStudyMethods() {
  methodsLoading.value = true
  try {
    methodsData.value = await learningAPI.getStudyMethods(courseId.value)
  } catch {
    // 错误已处理
  } finally {
    methodsLoading.value = false
  }
}

function onTabChange(name: string | number) {
  if (name === 'methods' && !methodsData.value) {
    fetchStudyMethods()
  }
}

function goAdaptivePractice() {
  router.push(`/course/${courseId.value}/practice?mode=adaptive`)
}

function goKpPractice(kpId: number) {
  if (!kpId) {
    ElMessage.warning('无法定位知识点')
    return
  }
  router.push(`/course/${courseId.value}/practice?mode=knowledge_point&kp_id=${kpId}`)
}

async function updateStatus(row: ProgressRecord, status: KnowledgeStatus) {
  try {
    await learningAPI.updateProgress({
      knowledge_point_id: row.knowledge_point_id,
      status,
      mastery_level: status === 'mastered' ? 1.0 : status === 'in_progress' ? 0.5 : 0.0,
    })
    row.status = status
    ElMessage.success('状态已更新')
    await fetchProgress()
  } catch {
    // 错误已处理
  }
}

onMounted(async () => {
  await fetchProgress()
  if (route.query.tab === 'recommend') {
    activeTab.value = 'recommend'
    fetchRecommend()
  }
})
</script>

<style scoped>
.progress-view {
  max-width: 900px;
  margin: 0 auto;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  border: none;
  background: none;
  color: var(--color-text-tertiary);
  font-family: inherit;
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 0;
  margin-bottom: var(--space-4);
  transition: color var(--duration-fast);
}

.back-link:hover {
  color: var(--color-text-primary);
}

.progress-header {
  margin-bottom: var(--space-8);
}

.page-title {
  font-size: var(--font-size-3xl);
  font-weight: 700;
  margin: 0;
  color: var(--color-text-primary);
}

.page-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin: var(--space-2) 0 0;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

@media (max-width: 600px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-5);
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  gap: var(--space-1);
}

.stat-value {
  font-size: var(--font-size-3xl);
  font-weight: 700;
  line-height: 1;
}

.stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.progress-bar-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-8);
  padding: var(--space-4) var(--space-5);
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
}

.progress-bar {
  flex: 1;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--color-surface-sunken);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-brand-600);
  border-radius: var(--radius-full);
  transition: width var(--duration-slow) var(--ease-out);
}

.progress-text {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-brand-600);
  white-space: nowrap;
}

.progress-tabs {
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
}

.kp-table-wrap {
  min-height: 200px;
}

.kp-cell-name {
  font-weight: 500;
  color: var(--color-text-primary);
}

.recommend-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.recommend-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  transition: background var(--duration-fast);
  flex-wrap: wrap;
}

.recommend-item:hover {
  background: var(--color-surface-overlay);
}

.recommend-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--color-brand-100);
  color: var(--color-brand-600);
  font-size: var(--font-size-sm);
  font-weight: 700;
  flex-shrink: 0;
}

html.dark .recommend-rank {
  background: rgba(99, 102, 241, 0.2);
  color: var(--color-brand-400);
}

.recommend-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.recommend-name {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.recommend-desc {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.recommend-reason {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: var(--space-1);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.inline-empty {
  padding: var(--space-10);
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
}

.methods-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.methods-summary {
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  background: var(--color-brand-50);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  margin: 0;
  line-height: var(--line-height-relaxed);
}

html.dark .methods-summary {
  background: rgba(99, 102, 241, 0.12);
}

.method-item {
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
}

.method-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.method-rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  background: var(--color-brand-100);
  color: var(--color-brand-600);
  font-size: var(--font-size-xs);
  font-weight: 700;
  flex-shrink: 0;
}

html.dark .method-rank {
  background: rgba(99, 102, 241, 0.2);
  color: var(--color-brand-400);
}

.method-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.method-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-2);
  line-height: var(--line-height-relaxed);
}

.method-reason {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin: 0;
}

.method-refresh {
  text-align: center;
}
.progress-view{max-width:1180px}.progress-header{padding:4px 2px 20px}.stats-row{gap:14px}.stat-card{border:1px solid #e4e8e2;border-radius:15px;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.04)}.stat-card:nth-child(1){background:#eff6ff;border-color:#bfdbfe}.stat-card:nth-child(2){background:#ecfdf3;border-color:#bbf7d0}.stat-card:nth-child(3){background:#fff7ed;border-color:#fed7aa}.stat-card:nth-child(4){background:#f5f3ff;border-color:#ddd6fe}.progress-bar-wrap,.kp-table-wrap,.recommend-wrap,.methods-wrap{border-color:#e4e8e2;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.035)}.recommend-item{background:#f5f9ff;border-color:#dbeafe}.method-item{background:#f5fcf7;border-color:#dcfce7}.progress-tabs{background:#fff;border:1px solid #e4e8e2;border-radius:15px;padding:8px 14px;box-shadow:0 3px 12px rgba(15,23,42,.035)}
</style>
