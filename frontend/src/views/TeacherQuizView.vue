<template>
  <div class="tq-view">
    <button class="back-link" @click="$router.back()"><el-icon :size="16"><ArrowLeft /></el-icon> 返回</button>

    <header class="tq-header">
      <h1 class="page-title">题库管理</h1>
      <p class="page-sub">AI 生成、审核与管理课程题目（仅教师）</p>
    </header>

    <div class="tq-toolbar">
      <el-select v-model="courseId" placeholder="选择课程" style="width: 240px" @change="onCourseChange">
        <el-option v-for="c in courses" :key="c.id" :label="c.title" :value="c.id" />
      </el-select>
      <el-select v-model="filterKp" placeholder="全部知识点" clearable style="width: 200px" @change="loadQuestions">
        <el-option v-for="kp in knowledgePoints" :key="kp.id" :label="kp.name" :value="kp.id" />
      </el-select>
      <el-select v-model="filterDifficulty" placeholder="全部难度" clearable style="width: 140px" @change="loadQuestions">
        <el-option label="基础" value="basic" />
        <el-option label="提高" value="advanced" />
      </el-select>
      <el-button type="primary" :disabled="!courseId" @click="openGenerate">AI 生成题目</el-button>
      <el-button :disabled="!courseId" @click="loadStats">使用统计</el-button>
    </div>

    <div class="tq-list" v-loading="loading">
      <div v-for="q in questions" :key="q.id" class="tq-item">
        <div class="tq-item-main">
          <div class="tq-item-tags">
            <el-tag size="small" :type="q.difficulty === 'advanced' ? 'warning' : 'info'">{{ q.difficulty === 'advanced' ? '提高' : '基础' }}</el-tag>
            <el-tag size="small" type="success">{{ typeLabel(q.question_type) }}</el-tag>
            <el-tag size="small">{{ q.knowledge_point_name }}</el-tag>
            <el-tag size="small" :type="q.is_active ? 'success' : 'danger'" effect="plain">{{ q.is_active ? '已启用' : '已停用' }}</el-tag>
          </div>
          <div class="tq-item-content">{{ q.content }}</div>
          <div class="tq-item-answer">答案：{{ q.correct_answer }}</div>
        </div>
        <div class="tq-item-actions">
          <el-button text size="small" @click="openEdit(q)">编辑</el-button>
          <el-button text size="small" :type="q.is_active ? 'warning' : 'success'" @click="toggleActive(q)">{{ q.is_active ? '停用' : '启用' }}</el-button>
          <el-button text size="small" type="danger" @click="removeQuestion(q)">删除</el-button>
        </div>
      </div>

      <div v-if="!loading && !questions.length" class="empty-state">
        <p>暂无题目，选择课程后点击「AI 生成题目」。</p>
      </div>
    </div>

    <!-- AI 生成 -->
    <el-dialog v-model="genVisible" title="AI 生成题目" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="知识点">
          <el-select v-model="genForm.knowledge_point_id" placeholder="选择知识点" style="width:100%">
            <el-option v-for="kp in knowledgePoints" :key="kp.id" :label="kp.name" :value="kp.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-radio-group v-model="genForm.difficulty">
            <el-radio value="basic">基础</el-radio>
            <el-radio value="advanced">提高</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="genForm.count" :min="1" :max="50" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="genVisible = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="generate">生成</el-button>
      </template>
    </el-dialog>

    <!-- 编辑题目 -->
    <el-dialog v-model="editVisible" title="编辑题目" width="640px" destroy-on-close>
      <div class="edit-dialog-intro"><span class="edit-dialog-icon">✎</span><div><strong>完善题目内容</strong><p>修改后会立即更新题库，学生下次练习即可看到。</p></div></div>
      <el-form label-position="top" class="edit-form">
        <el-form-item label="题干" required><el-input v-model="editForm.content" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="请输入题目描述" /></el-form-item>
        <el-form-item label="选项"><el-input v-model="editForm.optionsText" type="textarea" :rows="4" placeholder="每行一个选项，例如：&#10;A. ...&#10;B. ..." /></el-form-item>
        <div class="edit-form-row"><el-form-item label="正确答案"><el-input v-model="editForm.correct_answer" placeholder="如 A、A,C 或 true" /></el-form-item><el-form-item label="题目解析"><el-input v-model="editForm.explanation" placeholder="可选，帮助学生理解" /></el-form-item></div>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 使用统计 -->
    <el-dialog v-model="statsVisible" title="题目使用统计" width="640px">
      <div v-for="s in stats" :key="s.question_id" class="stats-row">
        <span class="stats-content">{{ s.content }}</span>
        <span class="stats-num">{{ s.attempt_count }}次 · 正确率{{ Math.round(s.accuracy * 100) }}%</span>
      </div>
      <div v-if="!stats.length" class="text-tertiary">暂无统计数据</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { coursesAPI, type CourseItem, type KnowledgePointItem } from '@/api/courses'
import { quizAPI } from '@/api/quiz'

const courses = ref<CourseItem[]>([])
const knowledgePoints = ref<KnowledgePointItem[]>([])
const courseId = ref<number | undefined>()
const filterKp = ref<number | undefined>()
const filterDifficulty = ref<string | undefined>()
const questions = ref<any[]>([])
const loading = ref(false)

const genVisible = ref(false)
const generating = ref(false)
const genForm = ref({ knowledge_point_id: undefined as number | undefined, difficulty: 'basic', count: 5 })

const editVisible = ref(false)
const editingId = ref(0)
const editForm = ref({ content: '', optionsText: '', correct_answer: '', explanation: '' })

const statsVisible = ref(false)
const stats = ref<any[]>([])

function typeLabel(t: string): string {
  const map: Record<string, string> = { single_choice: '单选', multiple_choice: '多选', true_false: '判断' }
  return map[t] || t
}

async function loadCourses() {
  try { courses.value = await coursesAPI.getList() } catch { courses.value = [] }
}

async function loadKnowledgePoints() {
  if (!courseId.value) { knowledgePoints.value = []; return }
  try {
    const detail = await coursesAPI.getDetail(courseId.value)
    knowledgePoints.value = (detail.knowledge_points || []).filter(kp => !(kp as any).is_module)
  } catch { knowledgePoints.value = [] }
}

async function loadQuestions() {
  if (!courseId.value) { questions.value = []; return }
  loading.value = true
  try {
    questions.value = await quizAPI.listQuestions(courseId.value, {
      kp_id: filterKp.value,
      difficulty: filterDifficulty.value as any,
    })
  } catch { questions.value = [] } finally { loading.value = false }
}

async function onCourseChange() {
  filterKp.value = undefined
  await Promise.all([loadKnowledgePoints(), loadQuestions()])
}

async function openGenerate() {
  if (!knowledgePoints.value.length) await loadKnowledgePoints()
  genForm.value = { knowledge_point_id: undefined, difficulty: 'basic', count: 5 }
  genVisible.value = true
}

async function generate() {
  if (!genForm.value.knowledge_point_id || !courseId.value) {
    ElMessage.warning('请选择知识点')
    return
  }
  generating.value = true
  try {
    const r = await quizAPI.generateQuestions({
      course_id: courseId.value,
      knowledge_point_id: genForm.value.knowledge_point_id,
      difficulty: genForm.value.difficulty as any,
      count: genForm.value.count,
    })
    ElMessage.success(`已生成 ${r.generated} 道题目`)
    genVisible.value = false
    loadQuestions()
  } catch { /* ignore */ } finally { generating.value = false }
}

function openEdit(q: any) {
  editingId.value = q.id
  editForm.value = {
    content: q.content,
    optionsText: (q.options || []).join('\n'),
    correct_answer: q.correct_answer,
    explanation: q.explanation || '',
  }
  editVisible.value = true
}

async function saveEdit() {
  try {
    await quizAPI.updateQuestion(editingId.value, {
      content: editForm.value.content,
      options: editForm.value.optionsText.split('\n').filter(Boolean),
      correct_answer: editForm.value.correct_answer,
      explanation: editForm.value.explanation,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    loadQuestions()
  } catch { /* ignore */ }
}

async function toggleActive(q: any) {
  try {
    await quizAPI.updateQuestion(q.id, { is_active: !q.is_active })
    ElMessage.success(q.is_active ? '已停用' : '已启用')
    loadQuestions()
  } catch { /* ignore */ }
}

async function removeQuestion(q: any) {
  try {
    await ElMessageBox.confirm('确定删除该题目？', '确认', { type: 'warning' })
    await quizAPI.deleteQuestion(q.id)
    ElMessage.success('已删除')
    loadQuestions()
  } catch { /* cancelled */ }
}

async function loadStats() {
  if (!courseId.value) return
  try {
    const r = await quizAPI.questionStats(courseId.value)
    stats.value = r.items
    statsVisible.value = true
  } catch { /* ignore */ }
}

onMounted(async () => {
  await loadCourses()
})
</script>

<style scoped>
.tq-view { max-width: 1000px; margin: 0 auto; }
.back-link { display: inline-flex; align-items: center; gap: 4px; border: none; background: none; color: #64748b; cursor: pointer; margin-bottom: 16px; }
.tq-header { margin-bottom: 20px; }
.page-title { font-size: 24px; font-weight: 700; margin: 0; }
.page-sub { font-size: 13px; color: #64748b; margin: 4px 0 0; }
.tq-toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.tq-list { display: flex; flex-direction: column; gap: 12px; }
.tq-item { display: flex; align-items: flex-start; justify-content: space-between; background: #fff; border: 1.5px solid #93c5fd; border-radius: 12px; padding: 14px; gap: 12px; }
.edit-dialog-intro{display:flex;align-items:center;gap:12px;padding:14px 16px;margin-bottom:20px;border:1px solid #fbcfe8;border-radius:12px;background:#fff7fb}.edit-dialog-icon{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;background:#fce7f3;color:#be185d;font-size:20px}.edit-dialog-intro strong{color:#831843}.edit-dialog-intro p{margin:3px 0 0;color:#9d174d;font-size:12px}.edit-form :deep(.el-form-item){margin-bottom:18px}.edit-form :deep(.el-form-item__label){color:#334155;font-weight:600}.edit-form :deep(.el-textarea__inner),.edit-form :deep(.el-input__wrapper){border-radius:10px}.edit-form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}.edit-form-row .el-form-item{min-width:0}@media(max-width:620px){.edit-form-row{grid-template-columns:1fr}}
.tq-item-main { flex: 1; min-width: 0; }
.tq-item-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.tq-item-content { font-size: 14px; font-weight: 500; margin-bottom: 6px; }
.tq-item-answer { font-size: 12px; color: #16a34a; }
.tq-item-actions { display: flex; flex-direction: column; flex-shrink: 0; }
.empty-state { text-align: center; padding: 60px; color: #94a3b8; }
.stats-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
.stats-content { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stats-num { flex-shrink: 0; color: #64748b; margin-left: 12px; }
.text-tertiary { color: #94a3b8; font-size: 13px; }
</style>
