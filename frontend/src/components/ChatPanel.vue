<template>
  <aside class="chat-panel" :class="{ open: isOpen }">
    <button class="chat-toggle" @click="toggle" :aria-label="isOpen ? '关闭问答' : '打开问答'">
      <el-icon :size="20"><ChatDotRound /></el-icon>
      <span v-if="!isOpen" class="toggle-badge" v-show="unreadCount > 0">{{ unreadCount }}</span>
    </button>

    <div class="chat-body" v-show="isOpen">
      <div class="chat-header">
        <span class="chat-header-title">AI 助教</span>
        <button class="chat-close" @click="close" aria-label="关闭">
          <el-icon :size="14"><Close /></el-icon>
        </button>
      </div>

      <div class="chat-messages" ref="messagesRef">
        <div v-if="messages.length === 0" class="chat-empty">
          <p>向我提问课程相关的问题</p>
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="chat-message"
          :class="msg.role"
        >
          <div class="message-bubble">
            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
            <div v-if="msg.references?.length" class="message-refs">
              <span class="ref-label">参考：</span>
              <span v-for="r in msg.references" :key="r.knowledge_point_id" class="ref-tag">
                {{ r.name }}
              </span>
            </div>
          </div>
        </div>

        <div v-if="loading" class="chat-message assistant">
          <div class="message-bubble typing">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="suggested-row" v-if="suggested.length && messages.length === 0">
          <button
            v-for="(q, idx) in suggested.slice(0, 3)"
            :key="idx"
            class="suggested-chip"
            @click="send(q)"
          >{{ q }}</button>
        </div>
        <div class="chat-input-row">
          <input
            v-model="inputText"
            type="text"
            class="chat-input"
            placeholder="输入问题..."
            @keydown.enter="send()"
            :disabled="loading"
          />
          <button
            class="chat-send"
            :disabled="!inputText.trim() || loading"
            @click="send()"
            aria-label="发送"
          >
            <el-icon :size="16"><Promotion /></el-icon>
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ChatDotRound, Close, Promotion } from '@element-plus/icons-vue'
import { qaAPI, type QAAnswer } from '@/api/qa'

const props = defineProps<{
  courseId?: number
  embedded?: boolean
}>()

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  references?: QAAnswer['references']
}

const isOpen = ref(false)
const inputText = ref('')
const messages = ref<ChatMessage[]>([])
const suggested = ref<string[]>([])
const loading = ref(false)
const messagesRef = ref<HTMLElement>()
const unreadCount = ref(0)

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    unreadCount.value = 0
    if (suggested.value.length === 0) {
      loadSuggested()
    }
  }
}

function close() {
  isOpen.value = false
}

async function loadSuggested() {
  try {
    const res = await qaAPI.getRecommendQuestions()
    suggested.value = res
  } catch {
    suggested.value = ['这门课程的核心知识点是什么？', '有哪些前置知识需要先掌握？', '如何高效学习这些知识点？']
  }
}

function renderMarkdown(text: string): string {
  // 简单的 Markdown 渲染：代码块、粗体、列表
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n- (.+)/g, '\n<li>$1</li>')
    .replace(/\n/g, '<br>')
}

async function send(text?: string) {
  const question = (text || inputText.value).trim()
  if (!question || loading.value) return

  messages.value.push({ role: 'user', content: question })
  inputText.value = ''
  loading.value = true

  await nextTick()
  scrollToBottom()

  try {
    const res = await qaAPI.ask(question, props.courseId)
    messages.value.push({
      role: 'assistant',
      content: res.answer,
      references: res.references,
    })
    if (res.suggested_questions?.length) {
      suggested.value = res.suggested_questions
    }
  } catch {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，暂时无法回答您的问题，请稍后重试。',
    })
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-panel {
  position: fixed;
  bottom: var(--space-6);
  right: var(--space-6);
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.chat-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-full);
  background: var(--color-brand-600);
  color: white;
  cursor: pointer;
  box-shadow: var(--shadow-lg);
  transition: all var(--duration-fast) var(--ease-out);
  position: relative;
}

.chat-toggle:hover {
  background: var(--color-brand-500);
  box-shadow: var(--shadow-xl);
  transform: translateY(-1px);
}

.toggle-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  background: var(--color-danger);
  color: white;
  font-size: 10px;
  font-weight: 600;
  border-radius: var(--radius-full);
}

.chat-body {
  position: absolute;
  bottom: 60px;
  right: 0;
  width: 400px;
  height: 520px;
  max-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.chat-header-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.chat-close {
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
}

.chat-close:hover {
  background: var(--color-surface-overlay);
  color: var(--color-text-primary);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.chat-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.chat-empty p {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
}

.chat-message.user .message-bubble {
  background: var(--color-brand-600);
  color: white;
  align-self: flex-end;
  max-width: 80%;
  margin-left: auto;
}

.chat-message.assistant .message-bubble {
  background: var(--color-surface-raised);
  color: var(--color-text-primary);
  max-width: 88%;
}

.message-bubble {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
}

.message-bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: var(--space-4) var(--space-4);
}

.typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  animation: typingBounce 1.2s ease-in-out infinite;
}

.typing .dot:nth-child(2) { animation-delay: 0.15s; }
.typing .dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.3; }
  30% { transform: translateY(-6px); opacity: 1; }
}

.message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.06);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
  overflow-x: auto;
  margin: var(--space-2) 0;
}

html.dark .message-text :deep(pre) {
  background: rgba(255, 255, 255, 0.06);
}

.message-text :deep(code) {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
}

.message-text :deep(li) {
  margin-left: var(--space-4);
}

.message-refs {
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

html.dark .message-refs {
  border-top-color: rgba(255, 255, 255, 0.06);
}

.ref-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.ref-tag {
  display: inline-block;
  padding: 1px var(--space-2);
  font-size: 11px;
  border-radius: var(--radius-sm);
  background: var(--color-brand-50);
  color: var(--color-brand-600);
}

html.dark .ref-tag {
  background: rgba(99, 102, 241, 0.12);
  color: var(--color-brand-400);
}

.chat-input-area {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.suggested-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.suggested-chip {
  display: inline-block;
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-xs);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-full);
  background: var(--color-surface-default);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-family: inherit;
}

.suggested-chip:hover {
  border-color: var(--color-brand-400);
  color: var(--color-brand-600);
  background: var(--color-brand-50);
}

.chat-input-row {
  display: flex;
  gap: var(--space-2);
}

.chat-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-md);
  background: var(--color-surface-overlay);
  font-family: inherit;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  outline: none;
  transition: border-color var(--duration-fast) var(--ease-out);
}

.chat-input:focus {
  border-color: var(--color-brand-400);
}

.chat-input::placeholder {
  color: var(--color-text-placeholder);
}

.chat-send {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-brand-600);
  color: white;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}

.chat-send:hover:not(:disabled) {
  background: var(--color-brand-500);
}

.chat-send:disabled {
  background: var(--color-surface-overlay);
  color: var(--color-text-placeholder);
  cursor: not-allowed;
}
</style>
