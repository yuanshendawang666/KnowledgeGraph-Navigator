<template>
  <div class="qa-view">
    <header class="qa-header">
      <h1 class="page-title">智能问答</h1>
      <p class="page-desc">基于知识图谱的 AI 助教，回答课程相关问题</p>
    </header>

    <div class="qa-layout">
      <!-- 对话区 -->
      <section class="qa-main">
        <div class="qa-messages" ref="messagesRef">
          <div v-if="messages.length === 0" class="qa-welcome">
            <div class="welcome-icon"><img src="/logo.png" alt="AI" class="welcome-logo" /></div>
            <h2 class="welcome-title">你好，我是 AI 助教</h2>
            <p class="welcome-desc">试试点击下方问题，或直接输入你的疑问</p>
            <div class="welcome-suggestions">
              <button
                v-for="(q, idx) in suggestedQuestions.slice(0, 6)"
                :key="idx"
                class="suggestion-chip"
                :style="chipStyle(idx)"
                @click="askQuestion(q)"
              >{{ q }}</button>
            </div>
          </div>

          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="qa-message"
            :class="msg.role"
          >
            <div class="msg-avatar">
              <span v-if="msg.role === 'user'" class="avatar-text">{{ auth.user?.username?.charAt(0)?.toUpperCase() }}</span>
              <img v-else src="/logo.png" alt="AI" class="avatar-icon-img" />
            </div>
            <div class="msg-body">
              <div class="msg-content" :class="msg.role" v-html="renderMarkdown(msg.content)"></div>
              <div v-if="msg.references?.length" class="msg-references">
                <span class="ref-title">参考：</span>
                <span v-for="(r, ridx) in msg.references" :key="r.name" class="ref-badge" :style="refBadgeStyle(ridx)">
                  {{ r.name }}
                </span>
              </div>
              <div v-if="msg.suggested?.length" class="msg-suggested">
                <button
                  v-for="(q, i) in msg.suggested.slice(0, 3)"
                  :key="i"
                  class="suggestion-chip small"
                  :style="chipStyle(i)"
                  @click="askQuestion(q)"
                >{{ q }}</button>
              </div>
            </div>
          </div>

          <div v-if="answering" class="qa-message assistant">
            <div class="msg-avatar">
              <img src="/logo.png" alt="AI" class="avatar-icon-img" />
            </div>
            <div class="msg-body">
              <div class="msg-content assistant typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
            </div>
          </div>
        </div>

        <div class="qa-input-area">
          <div class="qa-input-row">
            <input
              v-model="inputText"
              type="text"
              class="qa-input"
              placeholder="输入你的问题…"
              @keydown.enter="askQuestion()"
              :disabled="answering"
            />
            <button
              class="qa-send-btn"
              :disabled="!inputText.trim() || answering"
              @click="askQuestion()"
            >
              <el-icon :size="18"><Promotion /></el-icon>
            </button>
          </div>
        </div>
      </section>

      <!-- 侧边栏 -->
      <aside class="qa-sidebar">
        <div class="sidebar-section section-course">
          <h3 class="sidebar-title">课程上下文</h3>
          <p class="sidebar-desc">选择课程后回答更精准</p>
          <el-select
            v-model="selectedCourseId"
            placeholder="全部课程"
            clearable
            style="width: 100%"
            size="default"
            @change="newConversation(); loadSessions()"
          >
            <el-option v-for="c in courses" :key="c.id" :label="c.title" :value="c.id" />
          </el-select>
        </div>

        <div class="sidebar-section section-sessions">
          <div class="sessions-head">
            <h3 class="sidebar-title">对话历史</h3>
            <div class="sessions-head-actions">
              <el-dropdown v-if="activeSessionId" trigger="click" @command="handleExport">
                <button class="new-chat-btn"><el-icon :size="12"><Download /></el-icon> 导出 <el-icon :size="10"><ArrowDown /></el-icon></button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="markdown">导出 Markdown</el-dropdown-item>
                    <el-dropdown-item command="pdf">导出 PDF</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <button class="new-chat-btn primary" @click="newConversation"><el-icon :size="12"><Plus /></el-icon> 新对话</button>
            </div>
          </div>
          <div class="sessions-list" v-loading="sessionsLoading">
            <div
              v-for="(s, sidx) in sessions"
              :key="s.id"
              class="session-item"
              :class="{ active: s.id === activeSessionId }"
              :style="sessionItemStyle(sidx, s.id === activeSessionId)"
              @click="openSession(s.id)"
            >
              <span class="session-title">
                {{ s.title }}
                <span class="session-course-tag" :class="{ global: !s.course_id }">{{ courseTitle(s.course_id) }}</span>
              </span>
              <button class="session-rename" @click.stop="renameSession(s)" title="重命名"><el-icon :size="12"><EditPen /></el-icon></button>
              <button class="session-del" @click.stop="removeSession(s.id)" title="删除">×</button>
            </div>
            <div v-if="!sessions.length && !sessionsLoading" class="sessions-empty">
              暂无历史对话
            </div>
          </div>
        </div>

        <div class="sidebar-section section-questions">
          <h3 class="sidebar-title">推荐问题</h3>
          <div class="sidebar-suggestions">
            <button
              v-for="(q, idx) in displayedSuggestions"
              :key="idx"
              class="sidebar-suggestion"
              :style="sidebarSuggestionStyle(idx)"
              @click="askQuestion(q)"
            >{{ q }}</button>
          </div>
        </div>

        <div class="sidebar-section section-actions">
          <button class="clear-btn" @click="newConversation">
            <el-icon :size="14"><Delete /></el-icon>
            清空对话
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { Promotion, Delete, EditPen, ArrowDown, Plus, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { qaAPI, type QAAnswer } from '@/api/qa'
import { coursesAPI, type CourseItem } from '@/api/courses'
import { chatAPI, type ChatSession } from '@/api/chat'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  references?: QAAnswer['sources']
  suggested?: string[]
}

const chipColors = [
  { bg: '#eff6ff', border: '#93c5fd', text: '#2563eb' },
  { bg: '#f0fdf4', border: '#86efac', text: '#16a34a' },
  { bg: '#fffbeb', border: '#fcd34d', text: '#d97706' },
  { bg: '#faf5ff', border: '#d8b4fe', text: '#9333ea' },
  { bg: '#fff1f2', border: '#fda4af', text: '#e11d48' },
  { bg: '#ecfeff', border: '#67e8f9', text: '#0891b2' },
]

function chipStyle(idx: number) {
  const c = chipColors[idx % chipColors.length]
  return { background: c.bg, borderColor: c.border, color: c.text }
}

function sidebarSuggestionStyle(idx: number) {
  const c = chipColors[idx % chipColors.length]
  return { borderLeft: `3px solid ${c.border}`, background: c.bg, color: c.text }
}

function sessionItemStyle(idx: number, active: boolean) {
  const c = chipColors[idx % chipColors.length]
  if (active) {
    return {
      border: `1px solid ${c.border}`, borderLeft: `3px solid ${c.border}`,
      background: c.bg, color: c.text,
      boxShadow: `0 1px 3px ${c.border}66`,
    }
  }
  return { borderLeft: `3px solid ${c.border}`, background: c.bg, color: c.text }
}

const COLOR_LIST = ['#2563eb','#16a34a','#d97706','#9333ea','#e11d48','#0891b2','#c026d3','#ea580c']
function refBadgeStyle(idx: number) {
  const c = COLOR_LIST[idx % COLOR_LIST.length]
  return { background: c + '18', color: c, border: `1px solid ${c}40` }
}

function courseTitle(courseId: number | null | undefined): string {
  if (courseId == null) return '全局'
  return courses.value.find(c => c.id === courseId)?.title || '全局'
}

const inputText = ref('')
const messages = ref<ChatMsg[]>([])
const answering = ref(false)
const selectedCourseId = ref<number | undefined>()
const courses = ref<CourseItem[]>([])

// 会话（多轮对话）
const sessions = ref<ChatSession[]>([])
const activeSessionId = ref<number | undefined>()
const sessionsLoading = ref(false)
const suggestedQuestions = ref<string[]>([
  'Python 中的列表和元组有什么区别？',
  '什么是装饰器？怎么使用？',
  'Python 异常处理 try-except 怎么用？',
  '面向对象编程中的 self 是什么？',
  '迭代器和生成器的区别是什么？',
  '如何用 pip 安装和管理第三方库？',
])

const messagesRef = ref<HTMLElement>()

const displayedSuggestions = computed(() => suggestedQuestions.value.slice(0, 8))

function renderMarkdown(text: string): string {
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n- (.+)/g, '\n<li>$1</li>')
    .replace(/\n/g, '<br>')
}

async function askQuestion(text?: string) {
  const question = (text || inputText.value).trim()
  if (!question || answering.value) return

  // 若尚无活动会话，自动新建会话（未选课程时为全局会话）
  if (!activeSessionId.value) {
    await ensureSession()
  }

  messages.value.push({ role: 'user', content: question })
  inputText.value = ''
  answering.value = true

  await nextTick(); scrollToBottom()

  try {
    const res = await qaAPI.ask(question, selectedCourseId.value, activeSessionId.value)
    if (res.session_id) {
      activeSessionId.value = res.session_id
    }
    messages.value.push({
      role: 'assistant', content: res.answer,
      references: res.sources ?? res.references, suggested: res.suggested_questions,
    })
    if (res.suggested_questions?.length) {
      suggestedQuestions.value = [...new Set([...res.suggested_questions, ...suggestedQuestions.value])].slice(0, 10)
    }
    loadSessions()
  } catch {
    messages.value.push({ role: 'assistant', content: '抱歉，暂时无法回答这个问题，请稍后重试。' })
  } finally {
    answering.value = false
    await nextTick(); scrollToBottom()
  }
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    // 未选课程时加载全部会话；选中时按课程过滤
    sessions.value = await chatAPI.listSessions(selectedCourseId.value)
  } catch {
    sessions.value = []
  } finally {
    sessionsLoading.value = false
  }
}

async function ensureSession() {
  if (activeSessionId.value) return
  try {
    const s = await chatAPI.createSession(selectedCourseId.value)
    activeSessionId.value = s.id
    sessions.value.unshift(s)
  } catch {
    activeSessionId.value = undefined
  }
}

async function openSession(id: number) {
  activeSessionId.value = id
  // 同步该会话所属课程，保证继续追问的上下文正确（程序化赋值不触发 el-select 的 change）
  const s = sessions.value.find(x => x.id === id)
  if (s && s.course_id !== selectedCourseId.value) {
    selectedCourseId.value = s.course_id ?? undefined
  }
  messages.value = []
  try {
    const msgs = await chatAPI.getMessages(id)
    messages.value = msgs.map((m) => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
      references: m.references_json ? JSON.parse(m.references_json) : [],
    }))
  } catch {
    messages.value = []
  }
  await nextTick(); scrollToBottom()
}

function newConversation() {
  activeSessionId.value = undefined
  messages.value = []
}

async function removeSession(id: number) {
  try {
    await chatAPI.deleteSession(id)
    if (activeSessionId.value === id) newConversation()
    loadSessions()
  } catch {
    // ignore
  }
}

async function renameSession(s: ChatSession) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的对话标题', '重命名对话', {
      inputValue: s.title,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    const title = (value || '').trim()
    if (title && title !== s.title) {
      await chatAPI.renameSession(s.id, title)
      ElMessage.success('已重命名')
      loadSessions()
    }
  } catch {
    // 取消
  }
}

function handleExport(cmd: string) {
  if (cmd === 'markdown') exportMarkdown()
  else if (cmd === 'pdf') exportPdf()
}

function currentSessionTitle(): string {
  const s = sessions.value.find(x => x.id === activeSessionId.value)
  return s?.title || '对话'
}

async function exportMarkdown() {
  if (!activeSessionId.value) return
  try {
    const md = await chatAPI.exportMarkdown(activeSessionId.value)
    downloadBlob(new Blob([md], { type: 'text/markdown;charset=utf-8' }), `${currentSessionTitle()}.md`)
    ElMessage.success('Markdown 已导出')
  } catch {
    ElMessage.error('导出 Markdown 失败')
  }
}

async function exportPdf() {
  if (!activeSessionId.value) return
  try {
    const blob = await chatAPI.exportPdf(activeSessionId.value)
    downloadBlob(blob, `${currentSessionTitle()}.pdf`)
    ElMessage.success('PDF 已导出')
  } catch {
    ElMessage.error('导出 PDF 失败')
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const file = blob instanceof Blob ? blob : new Blob([blob], { type: 'application/octet-stream' })
  const url = URL.createObjectURL(file)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  a.remove()
  // 等浏览器完成下载初始化后再释放对象 URL，避免 PDF 下载为空或损坏。
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function scrollToBottom() {
  if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
}

onMounted(async () => {
  try {
    courses.value = await coursesAPI.getList()
  } catch {}
  await loadSessions()
  // 自动恢复最近一次对话（退出页面再进来不丢上下文）
  if (sessions.value.length) {
    await openSession(sessions.value[0].id)
  }
})
</script>

<style scoped>
.qa-view { max-width: 1100px; margin: 0 auto; }

.qa-header { margin-bottom: var(--space-6); }
.page-title { font-size: var(--font-size-3xl); font-weight: 700; margin: 0; color: var(--color-text-primary); }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-secondary); margin: var(--space-2) 0 0; }

.qa-layout { display: grid; grid-template-columns: 1fr 270px; gap: var(--space-6); align-items: start; }
@media (max-width: 800px) { .qa-layout { grid-template-columns: 1fr; } }

/* 主对话区 */
.qa-main {
  display: flex; flex-direction: column;
  height: calc(100vh - 200px); min-height: 500px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1.5px solid #bfdbfe; border-radius: var(--radius-xl); overflow: hidden;
}

.qa-messages { flex: 1; overflow-y: auto; padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-5); }

.qa-welcome { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: var(--space-10) var(--space-6); flex: 1; }
.welcome-icon { margin-bottom: var(--space-4); }
.welcome-logo { width: 56px; height: 56px; object-fit: contain; }
.welcome-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 0 0 var(--space-2); }
.welcome-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin: 0 0 var(--space-6); }
.welcome-suggestions { display: flex; flex-wrap: wrap; gap: var(--space-2); justify-content: center; max-width: 560px; }

.suggestion-chip {
  display: inline-block; padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-sm); border: 1px solid; border-radius: var(--radius-full);
  cursor: pointer; font-family: inherit; font-weight: 500;
  transition: all var(--duration-fast) var(--ease-out);
}
.suggestion-chip:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
.suggestion-chip.small { font-size: var(--font-size-xs); padding: var(--space-1) var(--space-3); }

/* 消息 */
.qa-message { display: flex; gap: var(--space-3); max-width: 88%; }
.qa-message.user { align-self: flex-end; flex-direction: row-reverse; }
.qa-message.assistant { align-self: flex-start; }

.msg-avatar {
  display: flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border-radius: var(--radius-full);
  flex-shrink: 0; font-size: var(--font-size-xs); font-weight: 600;
}
.qa-message.user .msg-avatar { background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; }
.qa-message.assistant .msg-avatar { background: transparent; }

.avatar-icon-img { width: 34px; height: 34px; object-fit: contain; }
.avatar-text { font-size: var(--font-size-sm); }

.msg-body { flex: 1; min-width: 0; }

.msg-content {
  padding: var(--space-3) var(--space-4); border-radius: var(--radius-lg);
  font-size: var(--font-size-sm); line-height: var(--line-height-relaxed);
}
.msg-content.user { background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; border-bottom-right-radius: var(--radius-sm); }
.msg-content.assistant { background: #f1f5f9; color: var(--color-text-primary); border-bottom-left-radius: var(--radius-sm); }

.msg-content :deep(pre) { background: rgba(0,0,0,0.04); padding: var(--space-2) var(--space-3); border-radius: 6px; font-family: var(--font-family-mono); font-size: var(--font-size-xs); overflow-x: auto; margin: var(--space-2) 0; }
.msg-content.user :deep(pre) { background: rgba(255,255,255,0.15); }
.msg-content :deep(code) { font-family: var(--font-family-mono); font-size: var(--font-size-xs); }
.msg-content :deep(li) { margin-left: var(--space-4); }

.typing-indicator { display: flex; align-items: center; gap: 4px; padding: var(--space-4); }
.typing-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-tertiary); animation: dotBounce 1.2s ease-in-out infinite; }
.typing-dot:nth-child(2) { animation-delay: 0.15s; }
.typing-dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes dotBounce { 0%,60%,100%{transform:translateY(0);opacity:.3} 30%{transform:translateY(-6px);opacity:1} }

.msg-references { margin-top: var(--space-2); display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-1); }
.ref-title { font-size: 11px; color: var(--color-text-tertiary); }
.ref-badge { display: inline-block; padding: 1px 8px; font-size: 11px; border-radius: var(--radius-full); font-weight: 500; }

.msg-suggested { margin-top: var(--space-3); display: flex; flex-wrap: wrap; gap: var(--space-2); }

/* 输入区 */
.qa-input-area { padding: var(--space-4) var(--space-5); border-top: 1px solid #e0f2fe; flex-shrink: 0; background: #fff; }
.qa-input-row { display: flex; gap: var(--space-2); }
.qa-input {
  flex: 1; padding: var(--space-3) var(--space-4);
  border: 1.5px solid #cbd5e1; border-radius: var(--radius-lg);
  background: #f8fafc; font-family: inherit; font-size: var(--font-size-sm);
  color: var(--color-text-primary); outline: none;
  transition: border-color var(--duration-fast);
}
.qa-input:focus { border-color: #3b82f6; background: #fff; }
.qa-input::placeholder { color: var(--color-text-placeholder); }

.qa-send-btn {
  display: flex; align-items: center; justify-content: center;
  width: 46px; height: 46px; border: none; border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #3b82f6, #2563eb); color: white;
  cursor: pointer; transition: all var(--duration-fast); flex-shrink: 0;
}
.qa-send-btn:hover:not(:disabled) { background: linear-gradient(135deg, #2563eb, #1d4ed8); transform: translateY(-1px); }
.qa-send-btn:disabled { background: #e2e8f0; color: #94a3b8; cursor: not-allowed; }

/* 侧边栏 */
.qa-sidebar { display: flex; flex-direction: column; gap: var(--space-4); }
.sidebar-section { border-radius: var(--radius-lg); padding: var(--space-4); border: 1.5px solid transparent; }
.section-course { background: #fff; border-color: #e2e8f0; }
.section-questions { background: #fff; border-color: #e2e8f0; }
.section-actions { background: #fff; border-color: #e2e8f0; padding: var(--space-3); }

.sidebar-title { font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-primary); margin: 0 0 var(--space-1); }
.sidebar-desc { font-size: var(--font-size-xs); color: var(--color-text-tertiary); margin: 0 0 var(--space-3); }

.sidebar-suggestions { display: flex; flex-direction: column; gap: var(--space-2); }
.sidebar-suggestion {
  display: block; text-align: left; width: 100%;
  padding: var(--space-2) var(--space-3); border-radius: var(--radius-md);
  border: none; font-family: inherit; font-size: var(--font-size-xs);
  cursor: pointer; font-weight: 500; transition: all var(--duration-fast);
}
.sidebar-suggestion:hover { filter: brightness(0.95); transform: translateX(2px); }

/* 会话列表 */
.section-sessions { background: #fff; border-color: #e2e8f0; }
.sessions-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2); }
.sessions-head-actions { display: flex; align-items: center; gap: 8px; }
.new-chat-btn {
  display: flex; align-items: center; gap: 3px;
  padding: 4px 10px; border: 1px solid #6ee7b7; border-radius: var(--radius-md);
  background: #fff; color: #059669;
  font-size: var(--font-size-xs); font-weight: 500; line-height: 1;
  cursor: pointer; font-family: inherit;
  transition: all var(--duration-fast) var(--ease-out);
}
.new-chat-btn:hover { background: #ecfdf5; border-color: #34d399; }
.new-chat-btn.primary {
  border: none;
  background: linear-gradient(135deg, #10b981, #059669); color: #fff;
  box-shadow: 0 1px 3px rgba(5, 150, 105, 0.35);
}
.new-chat-btn.primary:hover { background: linear-gradient(135deg, #059669, #047857); transform: translateY(-1px); box-shadow: 0 2px 6px rgba(5, 150, 105, 0.4); }
.sessions-list { display: flex; flex-direction: column; gap: var(--space-2); max-height: 220px; overflow-y: auto; }
.session-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md); border-left: 3px solid transparent;
  cursor: pointer; font-size: var(--font-size-xs); font-weight: 500;
  transition: all var(--duration-fast) var(--ease-out);
}
.session-item:hover { filter: brightness(0.95); transform: translateX(2px); }
.session-item.active { font-weight: 600; }
.session-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: flex; align-items: center; gap: 4px; min-width: 0; }
.session-course-tag {
  flex-shrink: 0; padding: 0 5px; border-radius: 4px;
  font-size: 10px; line-height: 16px; font-weight: 500;
  background: rgba(255, 255, 255, 0.7); color: inherit;
}
.session-course-tag.global { background: rgba(255, 255, 255, 0.5); opacity: 0.85; }
.session-del { border: none; background: none; color: inherit; opacity: 0.55; cursor: pointer; font-size: 16px; line-height: 1; flex-shrink: 0; transition: opacity var(--duration-fast); }
.session-del:hover { opacity: 1; color: #ef4444; }
.session-rename { border: none; background: none; color: inherit; opacity: 0.55; cursor: pointer; display: flex; align-items: center; flex-shrink: 0; padding: 0; transition: opacity var(--duration-fast); }
.session-rename:hover { opacity: 1; color: #2563eb; }
.sessions-empty { text-align: center; padding: 12px; color: #94a3b8; font-size: var(--font-size-xs); }

.clear-btn {
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
  width: 100%; padding: var(--space-2); border: 1.5px dashed #fca5a5;
  border-radius: var(--radius-md); background: #fff5f5; color: #ef4444;
  font-family: inherit; font-size: var(--font-size-xs); cursor: pointer; transition: all var(--duration-fast);
}
.clear-btn:hover { background: #fef2f2; border-color: #ef4444; }
.qa-view{max-width:1180px}.qa-header{padding:4px 2px 20px}.qa-layout{grid-template-columns:minmax(0,1fr) 300px;gap:20px}.qa-main{border:1px solid #dce8e1;border-radius:18px;background:linear-gradient(180deg,#fff,#fbfffc);box-shadow:0 5px 18px rgba(15,23,42,.05)}.qa-welcome{background:radial-gradient(circle at 50% 15%,#eff6ff,transparent 38%);border-radius:18px}.suggestion-chip{border-color:#bfdbfe;background:#eff6ff;color:#2563eb}.suggestion-chip:nth-child(2n){border-color:#bbf7d0;background:#ecfdf3;color:#15803d}.suggestion-chip:nth-child(3n){border-color:#fed7aa;background:#fff7ed;color:#c2410c}.qa-sidebar .sidebar-section{box-shadow:0 3px 12px rgba(15,23,42,.04);border-color:#e4e8e2}.section-course{background:#eff6ff;border-color:#bfdbfe!important}.section-questions{background:#fff7ed;border-color:#fed7aa!important}.section-actions{background:#ecfdf3;border-color:#bbf7d0!important}.section-sessions{background:#f5f3ff;border-color:#ddd6fe!important}.qa-input-area{background:#fbfcfa;border-top-color:#dce8e1}.qa-input:focus{border-color:#86efac;background:#fff}.qa-send-btn{background:linear-gradient(135deg,#22c55e,#15803d);box-shadow:0 5px 12px rgba(34,197,94,.2)}
</style>
