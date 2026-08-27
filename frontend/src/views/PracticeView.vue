<template>
  <div class="practice-view">
    <button class="back-link" @click="goBack">
      <el-icon :size="16"><ArrowLeft /></el-icon>
      返回
    </button>

    <!-- 配置阶段 -->
    <div v-if="phase === 'config'" class="config-panel">
      <header class="practice-header">
        <h1 class="page-title">智能练习</h1>
        <p class="page-desc">
          正确率 ≥ {{ masteryPercent }}% 视为掌握，可在下方调整题数
        </p>
      </header>

      <!-- 子 Tab：新练习 / 练习历史 -->
      <div class="sub-tabs">
        <button
          :class="['sub-tab', { active: configTab === 'new' }]"
          @click="configTab = 'new'"
        >开始练习</button>
        <button
          :class="['sub-tab', { active: configTab === 'history' }]"
          @click="switchToHistory"
        >练习历史</button>
      </div>

      <!-- 新练习面板 -->
      <div v-show="configTab === 'new'" class="config-card">
        <div class="config-row">
          <label>练习模式</label>
          <el-radio-group v-model="mode" @change="onModeChange">
            <el-radio value="adaptive">自适应（推荐知识点）</el-radio>
            <el-radio value="knowledge_point">指定知识点</el-radio>
            <el-radio value="wrong_book">错题重练</el-radio>
          </el-radio-group>
        </div>

        <div class="config-row" v-if="mode === 'knowledge_point'">
          <label>选择知识点</label>
          <el-select
            v-model="selectedKpId"
            placeholder="请选择知识点"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="kp in knowledgePoints"
              :key="kp.id"
              :label="kp.name"
              :value="kp.id"
            />
          </el-select>
          <span class="config-hint" v-if="!knowledgePoints.length">
            加载知识点中…
          </span>
        </div>

        <!-- 错题本预览 -->
        <div v-if="mode === 'wrong_book'" class="wrong-book-preview">
          <div class="wb-header">
            <span class="wb-title">错题本预览</span>
            <span class="wb-count" v-if="wrongBookItems.length">
              {{ wrongBookItems.length }} 道待复习错题
            </span>
          </div>
          <div v-if="wrongBookLoading" class="wb-loading">加载中…</div>
          <div v-else-if="wrongBookItems.length === 0" class="wb-empty">
            🎉 暂无未掌握的错题，将自动切换为自适应模式
          </div>
          <div v-else class="wb-list">
            <div v-for="item in wrongBookItems.slice(0, 6)" :key="item.wrong_id" class="wb-item">
              <span class="wb-kp">{{ item.knowledge_point_name }}</span>
              <span class="wb-content">{{ item.content }}</span>
              <el-tag size="small" type="danger" round>
                错 {{ item.wrong_count }} 次
              </el-tag>
            </div>
            <div v-if="wrongBookItems.length > 6" class="wb-more">
              还有 {{ wrongBookItems.length - 6 }} 道错题…
            </div>
          </div>
        </div>

        <div class="config-row">
          <label>难度</label>
          <el-radio-group v-model="difficulty">
            <el-radio value="basic">基础</el-radio>
            <el-radio value="advanced">提高</el-radio>
          </el-radio-group>
        </div>

        <div class="config-row">
          <label>题目总数：<strong>{{ count }}</strong> 道</label>
          <el-slider
            v-model="count"
            :min="1"
            :max="20"
            :step="1"
            :marks="{ 1: '1', 5: '5', 10: '10', 15: '15', 20: '20' }"
            show-stops
          />
        </div>

        <el-button
          type="primary"
          size="large"
          :loading="generating"
          @click="startPractice"
          class="start-btn"
        >
          开始练习
        </el-button>
      </div>

      <!-- 练习历史面板 -->
      <div v-show="configTab === 'history'" class="history-panel">
        <div v-if="historyLoading" class="history-loading">加载中…</div>
        <div v-else-if="historyItems.length === 0" class="history-empty">
          暂无练习记录
        </div>
        <div v-else class="history-list">
          <div
            v-for="h in historyItems"
            :key="h.session_id"
            class="history-item"
            @click="reviewSession(h.session_id)"
          >
            <div class="hi-left">
              <span class="hi-mode">{{ modeLabel(h.mode) }}</span>
              <span class="hi-meta">
                {{ h.total_count }} 题 ·
                {{ h.correct_count }} 对 ·
                {{ Math.round((h.score || 0) * 100) }}%
              </span>
            </div>
            <div class="hi-right">
              <el-tag
                :type="h.status === 'completed' ? 'success' : 'info'"
                size="small"
                round
              >
                {{ h.status === 'completed' ? '已完成' : h.status }}
              </el-tag>
              <span class="hi-date">{{ formatDate(h.started_at) }}</span>
              <el-icon :size="14"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 答题阶段 -->
    <div v-else-if="phase === 'quiz'" class="quiz-panel" v-loading="generating">
      <!-- …… 答题阶段不变 …… -->
      <header class="quiz-header">
        <h2 class="quiz-title">练习中</h2>
        <span class="quiz-meta">{{ session?.total_count || 0 }} 道题 · {{ difficultyLabel }}</span>
      </header>

      <div class="question-list">
        <div
          v-for="(q, idx) in session?.questions || []"
          :key="q.id"
          class="question-card"
        >
          <div class="q-header">
            <span class="q-index">{{ idx + 1 }}</span>
            <el-tag size="small" round>{{ typeLabel(q.question_type) }}</el-tag>
            <span class="q-kp">{{ q.knowledge_point_name }}</span>
          </div>
          <p class="q-content">{{ q.content }}</p>

          <!-- 判断题 -->
          <el-radio-group
            v-if="q.question_type === 'true_false'"
            v-model="answers[q.id]"
            class="option-group"
          >
            <el-radio value="true" class="option-item">正确</el-radio>
            <el-radio value="false" class="option-item">错误</el-radio>
          </el-radio-group>

          <!-- 单选题 -->
          <el-radio-group
            v-else-if="q.question_type === 'single_choice'"
            v-model="answers[q.id]"
            class="option-group"
          >
            <el-radio
              v-for="opt in q.options"
              :key="opt"
              :value="extractLetter(opt)"
              class="option-item"
            >{{ opt }}</el-radio>
          </el-radio-group>

          <!-- 多选题 -->
          <el-checkbox-group
            v-else
            v-model="multiAnswers[q.id]"
            class="option-group"
          >
            <el-checkbox
              v-for="opt in q.options"
              :key="opt"
              :value="extractLetter(opt)"
              class="option-item"
            >{{ opt }}</el-checkbox>
          </el-checkbox-group>
        </div>
      </div>

      <div class="quiz-actions">
        <el-button type="primary" size="large" :loading="submitting" @click="submitQuiz">
          提交答卷
        </el-button>
      </div>
    </div>

    <!-- 结果阶段 -->
    <div v-else-if="phase === 'result'" class="result-panel">
      <div class="result-card">
        <div class="result-score" :class="resultPassed ? 'pass' : 'fail'">
          {{ Math.round((result?.score || 0) * 100) }}%
        </div>
        <p class="result-summary">
          答对 {{ result?.correct_count }} / {{ result?.total_count }} 题
        </p>
        <p class="result-hint">
          掌握标准：正确率 ≥ {{ Math.round((result?.mastery_threshold || 0.9) * 100) }}%
        </p>

        <div v-if="result?.progress_updates?.length" class="progress-updates">
          <h3>掌握度更新</h3>
          <div
            v-for="u in result.progress_updates"
            :key="u.knowledge_point_id"
            class="update-item"
          >
            <span>知识点 #{{ u.knowledge_point_id }}</span>
            <el-tag :type="u.mastered ? 'success' : 'warning'" size="small" round>
              {{ u.mastered ? '已掌握' : '学习中' }} · {{ u.accuracy }}%
            </el-tag>
          </div>
        </div>

        <div class="result-detail">
          <h3>答题详情</h3>
          <div
            v-for="(r, idx) in result?.results || []"
            :key="r.question_id"
            class="detail-item"
            :class="r.is_correct ? 'correct' : 'wrong'"
          >
            <div class="detail-head">
              <span>第 {{ idx + 1 }} 题</span>
              <el-tag :type="r.is_correct ? 'success' : 'danger'" size="small">
                {{ r.is_correct ? '正确' : '错误' }}
              </el-tag>
            </div>
            <p v-if="!r.is_correct" class="detail-answer">
              你的答案：{{ r.user_answer || '未作答' }} · 正确答案：{{ formatAnswer(r.correct_answer) }}
            </p>
            <p v-if="r.explanation" class="detail-explanation">{{ r.explanation }}</p>
          </div>
        </div>

        <div class="result-actions">
          <el-button @click="resetPractice">再练一次</el-button>
          <el-button type="primary" @click="goToProgress">查看学习进度</el-button>
        </div>
      </div>
    </div>

    <!-- 历史回顾弹窗 -->
    <el-dialog
      v-model="reviewVisible"
      title="练习回顾"
      width="700px"
      destroy-on-close
    >
      <div v-if="reviewData" class="review-dialog">
        <div class="review-summary">
          <span>模式：{{ modeLabel(reviewData.mode) }}</span>
          <span>{{ reviewData.total_count }} 题</span>
          <span>正确率：{{ Math.round((reviewData.score || 0) * 100) }}%</span>
          <span>{{ formatDate(reviewData.started_at) }}</span>
        </div>
        <div class="review-questions">
          <div
            v-for="(q, idx) in reviewData.questions"
            :key="q.question_id"
            class="review-q-item"
            :class="q.is_correct ? 'correct' : 'wrong'"
          >
            <div class="rq-header">
              <span class="rq-index">{{ idx + 1 }}. {{ q.knowledge_point_name }}</span>
              <el-tag :type="q.is_correct ? 'success' : 'danger'" size="small">
                {{ q.is_correct ? '正确' : '错误' }}
              </el-tag>
            </div>
            <p class="rq-content">{{ q.content }}</p>
            <div v-if="!q.is_correct" class="rq-answer">
              <span>你的答案：{{ formatAnswer(q.user_answer) || '未作答' }}</span>
              <span class="rq-correct">正确答案：{{ formatAnswer(q.correct_answer) }}</span>
            </div>
            <p v-if="q.explanation" class="rq-explanation">{{ q.explanation }}</p>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { quizAPI, type QuizMode, type QuestionDifficulty, type QuizSession, type SubmitResult, type WrongBookItem, type SessionHistoryItem, type SessionReview } from '@/api/quiz'
import { coursesAPI } from '@/api/courses'

const route = useRoute()
const router = useRouter()

const courseId = computed(() => Number(route.params.id))
const questionsPerKp = 5
const masteryPercent = 90

const phase = ref<'config' | 'quiz' | 'result'>('config')
const configTab = ref<'new' | 'history'>('new')
const mode = ref<QuizMode>((route.query.mode as QuizMode) || 'adaptive')
const difficulty = ref<QuestionDifficulty>('basic')
const count = ref(5)  // 每个知识点的题目数量
const selectedKpId = ref<number | null>(
  route.query.kp_id ? Number(route.query.kp_id) : null,
)

const generating = ref(false)
const submitting = ref(false)
const session = ref<QuizSession | null>(null)
const result = ref<SubmitResult | null>(null)
const knowledgePoints = ref<Array<{ id: number; name: string }>>([])

// 错题本
const wrongBookItems = ref<WrongBookItem[]>([])
const wrongBookLoading = ref(false)

// 练习历史
const historyItems = ref<SessionHistoryItem[]>([])
const historyLoading = ref(false)

// 回顾弹窗
const reviewVisible = ref(false)
const reviewData = ref<SessionReview | null>(null)

const answers = reactive<Record<number, string>>({})
const multiAnswers = reactive<Record<number, string[]>>({})

const difficultyLabel = computed(() =>
  difficulty.value === 'advanced' ? '提高' : '基础',
)
const resultPassed = computed(() =>
  (result.value?.score || 0) >= (result.value?.mastery_threshold || 0.9),
)

function typeLabel(t: string): string {
  const map: Record<string, string> = {
    single_choice: '单选',
    multiple_choice: '多选',
    true_false: '判断',
  }
  return map[t] || t
}

function extractLetter(opt: string): string {
  const m = opt.match(/^([A-D])/i)
  return m ? m[1].toUpperCase() : opt
}

function formatAnswer(ans: string): string {
  if (ans === 'true') return '正确'
  if (ans === 'false') return '错误'
  return ans
}

function goBack() {
  router.push(`/progress/${courseId.value}`)
}

function goToProgress() {
  router.push(`/progress/${courseId.value}?tab=recommend`)
}

function resetPractice() {
  phase.value = 'config'
  configTab.value = 'new'
  session.value = null
  result.value = null
  Object.keys(answers).forEach(k => delete answers[Number(k)])
  Object.keys(multiAnswers).forEach(k => delete multiAnswers[Number(k)])
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

function modeLabel(m: string): string {
  const map: Record<string, string> = {
    adaptive: '自适应',
    knowledge_point: '指定知识点',
    wrong_book: '错题重练',
  }
  return map[m] || m
}

async function loadKnowledgePoints() {
  try {
    // 优先从课程详情获取知识点列表（无需学习记录）
    const course = await coursesAPI.getDetail(courseId.value)
    knowledgePoints.value = (course.knowledge_points || []).map(kp => ({
      id: kp.id,
      name: kp.name,
    }))
    if (!selectedKpId.value && knowledgePoints.value.length) {
      selectedKpId.value = knowledgePoints.value[0].id
    }
  } catch {
    knowledgePoints.value = []
  }
}

async function onModeChange(newMode: QuizMode) {
  if (newMode === 'wrong_book') {
    wrongBookLoading.value = true
    try {
      const res = await quizAPI.getWrongBook(courseId.value)
      wrongBookItems.value = res.items || []
    } catch {
      wrongBookItems.value = []
    } finally {
      wrongBookLoading.value = false
    }
  }
}

async function switchToHistory() {
  configTab.value = 'history'
  historyLoading.value = true
  try {
    historyItems.value = await quizAPI.getSessions(courseId.value)
  } catch {
    historyItems.value = []
  } finally {
    historyLoading.value = false
  }
}

async function reviewSession(sessionId: number) {
  try {
    reviewData.value = await quizAPI.reviewSession(sessionId)
    reviewVisible.value = true
  } catch {
    ElMessage.error('加载练习回顾失败')
  }
}

async function startPractice() {
  if (mode.value === 'knowledge_point' && !selectedKpId.value) {
    ElMessage.warning('请选择知识点')
    return
  }

  generating.value = true
  try {
    const payload: Parameters<typeof quizAPI.generate>[0] = {
      course_id: courseId.value,
      mode: mode.value,
      difficulty: difficulty.value,
      count: count.value,
    }
    if (mode.value === 'knowledge_point' && selectedKpId.value) {
      payload.knowledge_point_ids = [selectedKpId.value]
    }

    session.value = await quizAPI.generate(payload)

    for (const q of session.value.questions) {
      if (q.question_type === 'multiple_choice') {
        multiAnswers[q.id] = []
      } else {
        answers[q.id] = ''
      }
    }

    phase.value = 'quiz'
  } catch {
    // handled
  } finally {
    generating.value = false
  }
}

async function submitQuiz() {
  if (!session.value) return

  const answerList = session.value.questions.map(q => {
    let userAnswer = ''
    if (q.question_type === 'multiple_choice') {
      const selected = multiAnswers[q.id] || []
      userAnswer = selected.sort().join(',')
    } else {
      userAnswer = answers[q.id] || ''
    }
    return { question_id: q.id, user_answer: userAnswer }
  })

  const unanswered = answerList.filter(a => !a.user_answer).length
  if (unanswered > 0) {
    ElMessage.warning(`还有 ${unanswered} 道题未作答`)
    return
  }

  submitting.value = true
  try {
    result.value = await quizAPI.submit(session.value.session_id, answerList)
    phase.value = 'result'
    ElMessage.success('答卷已提交')
  } catch {
    // handled
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadKnowledgePoints()
})
</script>

<style scoped>
.practice-view {
  max-width: 720px;
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
}

.back-link:hover {
  color: var(--color-text-primary);
}

.practice-header {
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: var(--font-size-3xl);
  font-weight: 700;
  margin: 0;
}

.page-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin: var(--space-2) 0 0;
}

.config-card {
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.config-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.config-row label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-secondary);
}

.start-btn {
  width: 100%;
  margin-top: var(--space-2);
}

.quiz-header {
  margin-bottom: var(--space-6);
}

.quiz-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  margin: 0;
}

.quiz-meta {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.question-card {
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
}

.q-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.q-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--color-brand-100);
  color: var(--color-brand-600);
  font-size: var(--font-size-xs);
  font-weight: 700;
}

.q-kp {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-left: auto;
}

.q-content {
  font-size: var(--font-size-base);
  font-weight: 500;
  margin: 0 0 var(--space-4);
  line-height: var(--line-height-base);
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-start;
}

.option-item {
  display: block;
  width: 100%;
  margin: 0 !important;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  transition: background var(--duration-fast);
}

.option-item:hover {
  background: var(--color-surface-raised);
}

.quiz-actions {
  display: flex;
  justify-content: center;
  padding-bottom: var(--space-8);
}

.result-card {
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

.result-score {
  font-size: 3.5rem;
  font-weight: 800;
  text-align: center;
  line-height: 1;
}

.result-score.pass { color: var(--color-success); }
.result-score.fail { color: var(--color-warning); }

.result-summary,
.result-hint {
  text-align: center;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  margin: var(--space-2) 0;
}

.progress-updates,
.result-detail {
  margin-top: var(--space-6);
}

.progress-updates h3,
.result-detail h3 {
  font-size: var(--font-size-sm);
  font-weight: 600;
  margin: 0 0 var(--space-3);
}

.update-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) 0;
  font-size: var(--font-size-sm);
  border-bottom: 1px solid var(--color-border-subtle);
}

.detail-item {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-2);
  font-size: var(--font-size-sm);
}

.detail-item.correct { background: var(--color-success-light); }
.detail-item.wrong { background: var(--color-danger-light); }

.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-1);
}

.detail-answer {
  color: var(--color-danger);
  margin: var(--space-1) 0;
}

.detail-explanation {
  color: var(--color-text-secondary);
  margin: var(--space-1) 0 0;
}

.result-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
  margin-top: var(--space-6);
}

/* ---- 子 Tab ---- */
.sub-tabs {
  display: flex;
  gap: 0;
  margin-bottom: var(--space-5);
  border-bottom: 2px solid var(--color-border-subtle);
}

.sub-tab {
  padding: var(--space-2) var(--space-5);
  border: none;
  background: none;
  font-family: inherit;
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-tertiary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all var(--duration-fast);
}

.sub-tab:hover { color: var(--color-text-primary); }

.sub-tab.active {
  color: var(--color-brand-600);
  border-bottom-color: var(--color-brand-600);
}

.config-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

/* ---- 错题本预览 ---- */
.wrong-book-preview {
  padding: var(--space-4);
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-md);
}

.wb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.wb-title { font-size: var(--font-size-sm); font-weight: 600; color: #991b1b; }
.wb-count { font-size: var(--font-size-xs); color: var(--color-text-tertiary); }
.wb-loading, .wb-empty { font-size: var(--font-size-xs); color: var(--color-text-tertiary); padding: var(--space-2) 0; }

.wb-list { display: flex; flex-direction: column; gap: var(--space-1); }

.wb-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  padding: var(--space-1) 0;
}

.wb-kp {
  font-weight: 500;
  color: #991b1b;
  flex-shrink: 0;
  min-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-content {
  flex: 1;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-more { font-size: var(--font-size-xs); color: var(--color-text-tertiary); }

/* ---- 练习历史 ---- */
.history-panel { min-height: 200px; }
.history-loading, .history-empty {
  text-align: center;
  padding: var(--space-12);
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
}

.history-list { display: flex; flex-direction: column; gap: var(--space-2); }

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.history-item:hover {
  border-color: var(--color-brand-300);
  box-shadow: var(--shadow-sm);
}

.hi-left { display: flex; flex-direction: column; gap: 2px; }
.hi-mode { font-size: var(--font-size-sm); font-weight: 600; }
.hi-meta { font-size: var(--font-size-xs); color: var(--color-text-tertiary); }

.hi-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.hi-date {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

/* ---- 回顾弹窗 ---- */
.review-dialog { max-height: 60vh; overflow-y: auto; }

.review-summary {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface-raised);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.review-questions { display: flex; flex-direction: column; gap: var(--space-3); }

.review-q-item {
  padding: var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
}

.review-q-item.correct { background: var(--color-success-light); }
.review-q-item.wrong { background: var(--color-danger-light); }

.rq-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.rq-index { font-weight: 600; }

.rq-content {
  margin: var(--space-2) 0;
  font-weight: 500;
}

.rq-answer {
  margin: var(--space-1) 0;
  font-size: var(--font-size-xs);
}

.rq-correct {
  margin-left: var(--space-4);
  color: var(--color-success);
  font-weight: 600;
}

.rq-explanation {
  margin: var(--space-1) 0 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}
</style>
