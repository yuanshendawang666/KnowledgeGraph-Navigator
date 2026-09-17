<template>
  <div class="evaluate-view" v-loading="loading">
    <button class="back-link" @click="goBack">
      <el-icon :size="16"><ArrowLeft /></el-icon> 返回学习进度
    </button>

    <header class="eval-header">
      <h1 class="page-title">AI 对话评判</h1>
      <p class="page-subtitle">{{ kpName }}</p>
    </header>

    <!-- 对话区 -->
    <div class="eval-chat" ref="chatRef">
      <div v-if="!evalMessages.length && !evalResult" class="eval-empty">
        <el-icon class="is-loading" :size="20"><Loading /></el-icon>
        <span>AI 助教正在准备问题…</span>
      </div>
      <div v-for="(m, i) in evalMessages" :key="i" class="eval-msg" :class="m.role">
        <div class="eval-avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
        <div class="eval-bubble">{{ m.content }}</div>
      </div>
    </div>

    <!-- 输入区 -->
    <div v-if="evalActive" class="eval-input-bar">
      <el-input
        v-model="evalInput"
        placeholder="输入你的回答..."
        @keydown.enter="sendEval"
      />
      <el-button type="primary" :loading="evalSending" @click="sendEval">发送</el-button>
    </div>

    <!-- 评判结果 -->
    <div v-if="evalResult" class="eval-result-card">
      <el-alert type="success" :closable="false" show-icon>
        <template #title>
          掌握度：{{ evalResult.mastery }} 分（{{ statusText(evalResult.learning_status) }}）
        </template>
        <p v-if="evalResult.comment">{{ evalResult.comment }}</p>
        <p v-if="evalResult.weak_points?.length">薄弱点：{{ evalResult.weak_points.join('、') }}</p>
        <p v-if="evalResult.suggestions?.length">建议：{{ evalResult.suggestions.join('；') }}</p>
      </el-alert>
      <el-button type="primary" style="margin-top: 12px" @click="goBack">返回学习进度</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { learningAPI } from '@/api/learning'

const route = useRoute()
const router = useRouter()
const courseId = Number(route.params.id)
const kpId = Number(route.params.kpId)
const kpName = (route.query.name as string) || '知识点'

const evalId = ref('')
const evalMessages = ref<Array<{ role: 'assistant' | 'user'; content: string }>>([])
const evalInput = ref('')
const evalActive = ref(false)
const evalSending = ref(false)
const loading = ref(false)
const evalResult = ref<any>(null)
const chatRef = ref<HTMLElement>()

function statusText(s?: string): string {
  const map: Record<string, string> = { mastered: '已掌握', in_progress: '学习中', not_started: '未开始' }
  return map[s || ''] || s || ''
}

function goBack() {
  router.push(`/progress/${courseId}`)
}

async function scrollToBottom() {
  await nextTick()
  if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
}

async function startEvaluate() {
  loading.value = true
  try {
    const r = await learningAPI.evaluateStart(kpId)
    evalId.value = r.eval_id
    evalMessages.value.push({ role: 'assistant', content: r.question })
    evalActive.value = true
  } catch (e: any) {
    ElMessage.error('启动评判失败: ' + (e?.response?.data?.detail || ''))
  } finally {
    loading.value = false
  }
  await scrollToBottom()
}

async function sendEval() {
  const ans = evalInput.value.trim()
  if (!ans || evalSending.value) return
  evalMessages.value.push({ role: 'user', content: ans })
  evalInput.value = ''
  evalSending.value = true
  await scrollToBottom()
  try {
    const r = await learningAPI.evaluateReply(evalId.value, ans)
    if (r.status === 'continue') {
      if (r.comment) evalMessages.value.push({ role: 'assistant', content: r.comment })
      if (r.question) evalMessages.value.push({ role: 'assistant', content: r.question })
    } else {
      evalActive.value = false
      evalResult.value = r
    }
  } catch (e: any) {
    ElMessage.error('评判失败: ' + (e?.response?.data?.detail || ''))
  } finally {
    evalSending.value = false
  }
  await scrollToBottom()
}

onMounted(startEvaluate)
</script>

<style scoped>
.evaluate-view { max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; min-height: calc(100vh - 100px); }

.back-link {
  display: inline-flex; align-items: center; gap: var(--space-2);
  border: none; background: none; color: var(--color-text-tertiary);
  font-family: inherit; font-size: var(--font-size-sm); cursor: pointer;
  padding: 0; margin-bottom: var(--space-4); transition: color var(--duration-fast);
  align-self: flex-start;
}
.back-link:hover { color: var(--color-text-primary); }

.eval-header { margin-bottom: var(--space-6); }
.page-title { font-size: var(--font-size-2xl); font-weight: 700; margin: 0; color: var(--color-text-primary); }
.page-subtitle { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin: var(--space-2) 0 0; }

.eval-chat {
  flex: 1; display: flex; flex-direction: column; gap: var(--space-4);
  overflow-y: auto; padding: var(--space-5);
  background: var(--color-surface-default); border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-lg); min-height: 300px;
}

.eval-empty { display: flex; align-items: center; gap: var(--space-2); color: var(--color-text-tertiary); font-size: var(--font-size-sm); padding: var(--space-6); }

.eval-msg { display: flex; gap: var(--space-3); }
.eval-msg.user { flex-direction: row-reverse; }
.eval-avatar {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: var(--radius-full);
  font-size: var(--font-size-xs); font-weight: 600; flex-shrink: 0;
}
.eval-msg.assistant .eval-avatar { background: var(--color-brand-100); color: var(--color-brand-600); }
.eval-msg.user .eval-avatar { background: var(--color-brand-600); color: #fff; }
.eval-bubble {
  max-width: 78%; padding: 10px 14px; border-radius: 12px;
  font-size: var(--font-size-sm); line-height: var(--line-height-relaxed); white-space: pre-wrap;
}
.eval-msg.assistant .eval-bubble { background: var(--color-surface-raised); border: 1px solid var(--color-border-subtle); }
.eval-msg.user .eval-bubble { background: var(--color-brand-600); color: #fff; }

.eval-input-bar { display: flex; gap: var(--space-2); margin-top: var(--space-4); }

.eval-result-card { margin-top: var(--space-4); }
.eval-result-card :deep(p) { margin: 4px 0; font-size: var(--font-size-sm); }
</style>
