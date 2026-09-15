<template>
  <div class="kp-detail" v-loading="loading">
    <button class="back-link" @click="$router.back()"><el-icon :size="16"><ArrowLeft /></el-icon> 返回</button>

    <header class="detail-header">
      <h1>{{ kp?.name }}</h1>
      <div class="header-meta">
        <el-tag v-if="kp?.level === 0" type="primary" size="small">模块</el-tag>
        <el-tag v-else-if="kp?.level === 1" size="small" style="background:#eef2ff;color:#4f46e5;border-color:#c7d2fe">子模块</el-tag>
        <el-tag v-else size="small" type="info">知识点</el-tag>
        <el-tag v-if="kp?.course_title" size="small" type="success">{{ kp.course_title }}</el-tag>
        <span class="meta-text">{{ statusLabel }}</span>
      </div>
      <div class="header-actions">
        <el-button size="small" @click="markMastered">标记已掌握</el-button>
        <el-button size="small" type="primary" @click="startEvaluate">开始评判</el-button>
        <el-button size="small" type="success" @click="openAsk">AI 提问</el-button>
      </div>
    </header>

    <div class="detail-content">
      <!-- 简介 -->
      <section class="card">
        <h2>简介</h2>
        <p>{{ kp?.description || '暂无简介' }}</p>
        <el-button v-if="auth.isTeacher" text size="small" type="primary" @click="enhanceDesc" style="margin-top:8px">
          <el-icon :size="14"><MagicStick /></el-icon> AI 优化简介
        </el-button>
      </section>

      <!-- AI 讲解内容 -->
      <section class="card">
        <div class="card-head">
          <h2>AI 讲解</h2>
          <el-button text size="small" type="primary" :loading="aiLoading" @click="generateAI">
            <el-icon :size="14"><MagicStick /></el-icon> {{ aiContent ? '重新生成' : '生成讲解' }}
          </el-button>
        </div>
        <div v-if="aiContent">
          <div class="ai-block" v-html="renderMarkdown(aiContent.explanation)"></div>
          <template v-if="aiContent.examples?.length">
            <h3>典型例题</h3>
            <ul><li v-for="(e, i) in aiContent.examples" :key="i">{{ e }}</li></ul>
          </template>
          <template v-if="aiContent.pitfalls?.length">
            <h3>常见误区</h3>
            <ul><li v-for="(p, i) in aiContent.pitfalls" :key="i">{{ p }}</li></ul>
          </template>
        </div>
        <p v-else class="text-tertiary">点击「生成讲解」，AI 将生成详细讲解、例题与常见误区。</p>
      </section>

      <!-- 邻接子图 -->
      <section class="card" v-if="kp?.neighbors?.length">
        <h2>关联知识点</h2>
        <div class="neighbor-list">
          <el-tag
            v-for="n in kp.neighbors"
            :key="n.neo4j_id"
            :type="n.relation === 'PREREQUISITE' ? 'warning' : n.relation === 'PART_OF' ? 'success' : 'info'"
            size="small"
            style="margin:2px"
          >{{ n.name }} <span class="rel">{{ relLabel(n.relation) }}</span></el-tag>
        </div>
      </section>

      <!-- 关联文档 -->
      <section class="card" v-if="kp?.documents?.length">
        <h2>关联文档</h2>
        <div v-for="d in kp.documents" :key="d.id" class="doc-item">
          <el-icon :size="14" style="margin-right:6px"><Document /></el-icon>
          <span class="doc-name">{{ d.filename }}</span>
          <span class="doc-status" :class="d.status">{{ docStatusLabel(d.status) }}</span>
        </div>
      </section>

      <!-- 学习笔记 -->
      <section class="card">
        <h2>学习笔记</h2>
        <div class="note-form">
          <el-input v-model="newNote.title" placeholder="笔记标题" size="small" style="margin-bottom:4px" />
          <el-input v-model="newNote.content" type="textarea" :rows="3" placeholder="笔记内容..." size="small" />
          <el-button size="small" type="primary" @click="addNote" style="margin-top:6px">添加笔记</el-button>
        </div>
        <div v-for="n in notes" :key="n.id" class="note-item">
          <strong>{{ n.title }}</strong>
          <span class="note-meta">{{ n.username }} · {{ (n.created_at || '').slice(0,10) }}</span>
          <p>{{ n.content }}</p>
          <el-button v-if="n.user_id === auth.user?.id" text size="small" type="danger" @click="deleteNote(n.id)">删除</el-button>
        </div>
        <p v-if="!notes.length" class="text-tertiary">暂无笔记</p>
      </section>
    </div>

    <!-- 评判对话 -->
    <el-dialog v-model="evalVisible" title="对话式掌握度评判" width="520px" :close-on-click-modal="false">
      <div class="eval-body">
        <div class="eval-history" ref="evalRef">
          <div v-for="(m, i) in evalMessages" :key="i" class="eval-msg" :class="m.role">
            <div class="eval-bubble">{{ m.content }}</div>
          </div>
        </div>
        <div class="eval-input" v-if="evalActive">
          <el-input v-model="evalAnswer" placeholder="输入你的回答..." @keydown.enter="sendEval" />
          <el-button type="primary" :loading="evalSending" @click="sendEval">发送</el-button>
        </div>
        <div v-if="evalResult" class="eval-result">
          <el-alert type="success" :closable="false" show-icon>
            <template #title>综合掌握度：{{ evalResult.mastery }} 分（{{ statusText(evalResult.learning_status) }}）</template>
            <p>{{ evalResult.comment }}</p>
            <p v-if="evalResult.weak_points?.length">薄弱点：{{ evalResult.weak_points.join('、') }}</p>
            <p v-if="evalResult.suggestions?.length">建议：{{ evalResult.suggestions.join('；') }}</p>
          </el-alert>
        </div>
      </div>
    </el-dialog>

    <!-- AI 提问 -->
    <el-dialog v-model="askVisible" :title="`AI 提问：${kp?.name || ''}`" width="560px">
      <div class="ask-body">
        <div class="ask-input">
          <el-input v-model="askQuestion" type="textarea" :rows="2" placeholder="针对该知识点提问..." />
          <el-button type="primary" :loading="askLoading" @click="sendAsk">提问</el-button>
        </div>
        <div v-if="askAnswer" class="ask-answer" v-html="renderMarkdown(askAnswer)"></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, MagicStick, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { knowledgeAPI, type KnowledgeDetail, type AIContent } from '@/api/knowledge'
import { notesAPI } from '@/api/notes'
import { learningAPI } from '@/api/learning'
import { qaAPI } from '@/api/qa'

const route = useRoute()
const auth = useAuthStore()
const kpId = Number(route.params.kpId)

const kp = ref<KnowledgeDetail | null>(null)
const notes = ref<Array<any>>([])
const loading = ref(false)
const newNote = ref({ title: '', content: '' })

const aiContent = ref<AIContent | null>(null)
const aiLoading = ref(false)

const statusLabel = computed(() => {
  const s = kp.value?.status
  return s === 'mastered' ? '✅ 已掌握' : s === 'in_progress' ? '🔄 学习中' : '⬜ 未开始'
})

function renderMarkdown(text: string): string {
  if (!text) return ''
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n- (.+)/g, '\n<li>$1</li>')
    .replace(/\n/g, '<br>')
}

function relLabel(r: string): string {
  const map: Record<string, string> = { PREREQUISITE: '先修', PART_OF: '包含', RELATED_TO: '相关' }
  return map[r] || r
}

function docStatusLabel(s: string): string {
  const map: Record<string, string> = { uploaded: '已上传', parsed: '已解析', extracted: '已提取', failed: '失败' }
  return map[s] || s
}

async function load() {
  loading.value = true
  try {
    kp.value = await knowledgeAPI.detail(kpId)
    notes.value = await notesAPI.list({ kp_id: kpId, course_id: kp.value.course_id })
  } catch { /* 错误已在拦截器提示 */ } finally { loading.value = false }
}

async function generateAI() {
  aiLoading.value = true
  try {
    aiContent.value = await knowledgeAPI.aiContent(kpId)
  } catch (e: any) {
    ElMessage.error('生成失败: ' + (e?.response?.data?.detail || ''))
  } finally { aiLoading.value = false }
}

async function markMastered() {
  if (!kp.value) return
  try {
    await learningAPI.updateProgress({ knowledge_point_id: kpId, status: 'mastered', mastery_level: 1.0 })
    kp.value.status = 'mastered'
    kp.value.mastery_level = 1.0
    ElMessage.success('已标记为掌握')
  } catch { /* ignore */ }
}

async function enhanceDesc() {
  if (!kp.value) return
  try {
    const r: any = await (await import('@/api/index')).default.post(
      `/courses/${kp.value.course_id}/knowledge-points/${kpId}/enhance`)
    kp.value.description = r.enhanced_description
    ElMessage.success('简介已优化')
  } catch (e: any) { ElMessage.error('优化失败: ' + (e?.response?.data?.detail || '')) }
}

async function addNote() {
  if (!newNote.value.title || !kp.value) return
  try {
    await notesAPI.create({ knowledge_point_id: kpId, course_id: kp.value.course_id, ...newNote.value })
    newNote.value = { title: '', content: '' }
    notes.value = await notesAPI.list({ kp_id: kpId, course_id: kp.value.course_id })
    ElMessage.success('笔记已添加')
  } catch { /* ignore */ }
}

async function deleteNote(id: number) {
  try {
    await notesAPI.remove(id)
    notes.value = notes.value.filter(n => n.id !== id)
  } catch { /* ignore */ }
}

// ── 对话式评判 ──
const evalVisible = ref(false)
const evalMessages = ref<Array<{ role: 'assistant' | 'user'; content: string }>>([])
const evalAnswer = ref('')
const evalActive = ref(false)
const evalSending = ref(false)
const evalResult = ref<any>(null)
const evalId = ref('')
const evalRef = ref<HTMLElement>()

function statusText(s?: string): string {
  const map: Record<string, string> = { mastered: '已掌握', in_progress: '学习中', not_started: '未开始' }
  return map[s || ''] || s || ''
}

async function startEvaluate() {
  evalVisible.value = true
  evalMessages.value = []
  evalResult.value = null
  evalActive.value = false
  evalAnswer.value = ''
  try {
    const r = await learningAPI.evaluateStart(kpId)
    evalId.value = r.eval_id
    evalMessages.value.push({ role: 'assistant', content: r.question })
    evalActive.value = true
  } catch (e: any) {
    ElMessage.error('启动评判失败: ' + (e?.response?.data?.detail || ''))
    evalVisible.value = false
  }
  scrollEval()
}

async function sendEval() {
  const ans = evalAnswer.value.trim()
  if (!ans || evalSending.value) return
  evalMessages.value.push({ role: 'user', content: ans })
  evalAnswer.value = ''
  evalSending.value = true
  await nextTick(); scrollEval()
  try {
    const r = await learningAPI.evaluateReply(evalId.value, ans)
    if (r.status === 'continue') {
      if (r.comment) evalMessages.value.push({ role: 'assistant', content: r.comment })
      if (r.question) evalMessages.value.push({ role: 'assistant', content: r.question })
    } else {
      evalActive.value = false
      evalResult.value = r
      kp.value!.status = r.learning_status as any
    }
  } catch (e: any) {
    ElMessage.error('评判失败: ' + (e?.response?.data?.detail || ''))
  } finally {
    evalSending.value = false
    await nextTick(); scrollEval()
  }
}

function scrollEval() {
  if (evalRef.value) evalRef.value.scrollTop = evalRef.value.scrollHeight
}

// ── AI 提问 ──
const askVisible = ref(false)
const askQuestion = ref('')
const askAnswer = ref('')
const askLoading = ref(false)

function openAsk() {
  askQuestion.value = kp.value ? `请讲解一下「${kp.value.name}」` : ''
  askAnswer.value = ''
  askVisible.value = true
}

async function sendAsk() {
  const q = askQuestion.value.trim()
  if (!q || askLoading.value || !kp.value) return
  askLoading.value = true
  try {
    const res = await qaAPI.ask(q, kp.value.course_id)
    askAnswer.value = res.answer
  } catch {
    askAnswer.value = '抱歉，暂时无法回答，请稍后重试。'
  } finally {
    askLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kp-detail { max-width: 860px; margin: 0 auto; }
.back-link { display: inline-flex; align-items: center; gap: 4px; border: none; background: none; color: #64748b; cursor: pointer; margin-bottom: 16px; }
.detail-header { margin-bottom: 24px; }
.detail-header h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
.header-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.meta-text { font-size: 13px; color: #64748b; }
.card { background: #fff; border: 1.5px solid #93c5fd; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
.card h2 { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.card h3 { font-size: 14px; font-weight: 600; margin: 12px 0 6px; }
.card-head { display: flex; align-items: center; justify-content: space-between; }
.ai-block { background: #f8fafc; padding: 12px; border-radius: 8px; line-height: 1.7; }
.note-item { padding: 12px 0; border-bottom: 1px solid #e2e8f0; }
.note-item strong { display: block; font-size: 14px; }
.note-item p { font-size: 13px; color: #475569; margin-top: 4px; }
.note-meta { font-size: 11px; color: #94a3b8; }
.note-form { margin-bottom: 12px; padding: 12px; background: #f8fafc; border-radius: 8px; }
.text-tertiary { color: #94a3b8; font-size: 13px; }
.rel { font-size: 10px; opacity: 0.7; }

.eval-body { display: flex; flex-direction: column; gap: 12px; }
.eval-history { max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.eval-msg { display: flex; }
.eval-msg.user { justify-content: flex-end; }
.eval-bubble { max-width: 80%; padding: 8px 12px; border-radius: 10px; font-size: 13px; line-height: 1.5; }
.eval-msg.assistant .eval-bubble { background: #f1f5f9; }
.eval-msg.user .eval-bubble { background: #3b82f6; color: #fff; }
.eval-input { display: flex; gap: 8px; }
.eval-result p { margin: 4px 0; font-size: 13px; }

.doc-item { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.doc-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-status { font-size: 11px; padding: 1px 8px; border-radius: 10px; flex-shrink: 0; }
.doc-status.extracted { background: #dcfce7; color: #15803d; }
.doc-status.parsed { background: #f0fdf4; color: #16a34a; }
.doc-status.uploaded { background: #eff6ff; color: #2563eb; }
.doc-status.failed { background: #fef2f2; color: #dc2626; }

.ask-body { display: flex; flex-direction: column; gap: 12px; }
.ask-input { display: flex; gap: 8px; align-items: flex-start; }
.ask-input .el-input { flex: 1; }
.ask-answer { background: #f8fafc; padding: 12px; border-radius: 8px; line-height: 1.7; font-size: 14px; }
</style>
