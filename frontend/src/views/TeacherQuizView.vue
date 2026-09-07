<template>
  <div class="tq-view">
    <button class="back-link" @click="$router.back()"><el-icon :size="16"><ArrowLeft /></el-icon> 返回</button>

    <header class="tq-header">
      <span class="section-kicker">教学资源工作台</span><h1 class="page-title">题库管理</h1>
      <p class="page-sub">AI 生成、审核与管理课程题目（仅教师）</p>
    </header>

    <div class="tq-toolbar"><div class="filter-heading"><strong>筛选题目</strong><span>按课程、知识点与难度定位教学内容</span></div>
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

    <div class="list-heading"><strong>课程题目</strong><span>当前筛选 {{ questions.length }} 道 · 已启用 {{ questions.filter(q => q.is_active).length }} 道</span></div>
    <div class="tq-list" v-loading="loading">
      <div v-for="(q, index) in questions" :key="q.id" class="tq-item">
        <span class="question-index">{{ String(index + 1).padStart(2, '0') }}</span><div class="tq-item-main">
          <div class="tq-item-tags">
            <el-tag size="small" :type="q.difficulty === 'advanced' ? 'warning' : 'info'">{{ q.difficulty === 'advanced' ? '提高' : '基础' }}</el-tag>
            <el-tag size="small" type="success">{{ typeLabel(q.question_type) }}</el-tag>
            <el-tag size="small">{{ q.knowledge_point_name }}</el-tag>
            <el-tag size="small" :type="q.is_active ? 'success' : 'danger'" effect="plain">{{ q.is_active ? '已启用' : '已停用' }}</el-tag>
          </div>
          <div class="tq-item-content">{{ q.content }}</div>
          <div v-if="q.options?.length" class="tq-options"><div v-for="(option, optionIndex) in q.options" :key="optionIndex">{{ option }}</div></div>
          <div class="tq-item-answer"><span>参考答案</span>{{ q.correct_answer || '未设置' }}</div>
          <details v-if="q.explanation" class="tq-explanation"><summary>查看解析</summary><p>{{ q.explanation }}</p></details>
        </div>
        <div class="tq-item-actions">
          <el-button text size="small" @click="openEdit(q)">编辑</el-button>
          <el-button text size="small" :type="q.is_active ? 'warning' : 'success'" @click="toggleActive(q)">{{ q.is_active ? '停用' : '启用' }}</el-button>
          <el-button text size="small" type="danger" @click="removeQuestion(q)">删除</el-button>
        </div>
      </div>

      <div v-if="!loading && !questions.length" class="empty-state">
        <div class="empty-symbol">?</div><strong>{{ courseId ? '当前筛选暂无题目' : '先选择一门课程' }}</strong><p>{{ courseId ? '调整筛选条件，或使用 AI 生成新的练习题。' : '在这里集中审核题目、查看答案并管理使用状态。' }}</p>
      </div>
    </div>

    <!-- AI 生成 -->
    <el-dialog v-model="genVisible" title="AI 生成题目" width="min(540px, 94vw)" destroy-on-close>
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
    <el-dialog v-model="editVisible" title="编辑题目" width="min(720px, 94vw)" destroy-on-close>
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
    <el-dialog v-model="statsVisible" title="题目使用统计" width="min(720px, 94vw)">
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
.tq-view { max-width: 1160px; margin: 0 auto; padding: 6px 0 40px; color: #4a3d48; --el-color-primary: #b34f79; --el-color-primary-light-9: #fcf0f5; }
.back-link { display: inline-flex; align-items: center; gap: 5px; border: 0; background: transparent; color: #8b998e; padding: 0; margin-bottom: 20px; cursor: pointer; font: inherit; font-size: 12px; }
.tq-header { margin-bottom: 28px; }
.section-kicker { color: #b34f79; font-size: 12px; font-weight: 700; letter-spacing: 2px; }
.page-title { font-size: 30px; color: #4c3045; margin: 6px 0; letter-spacing: -.7px; }
.page-sub { font-size: 14px; color: #819087; margin: 8px 0 0; }
.tq-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 22px; background: #fff; border: 1px solid #e0e8e2; border-radius: 12px; margin-bottom: 26px; }
.filter-heading { flex-basis: 100%; display: flex; align-items: baseline; flex-wrap: wrap; gap: 14px; margin-bottom: 5px; }
.filter-heading strong { font-size: 15px; }
.filter-heading span { font-size: 12px; color: #8c9a90; }
.tq-view :deep(.el-button) { border-radius: 8px; box-shadow: none; font-weight: 600; }
.tq-view :deep(.el-button--primary:not(.is-text)) { background: #b34f79; border-color: #b34f79; }
.tq-view :deep(.el-select__wrapper), .tq-view :deep(.el-input__wrapper) { min-height: 40px; border-radius: 8px; box-shadow: 0 0 0 1px #dce6df inset; }
.tq-view :deep(.el-textarea__inner) { line-height: 1.75; padding: 12px; border-radius: 8px; box-shadow: 0 0 0 1px #dce6df inset; }
.tq-toolbar .el-select { max-width: 100%; }
.list-heading { display: flex; align-items: center; justify-content: space-between; gap: 15px; flex-wrap: wrap; margin-bottom: 16px; }
.list-heading strong { font-size: 16px; }
.list-heading span { font-size: 12px; color: #8c998f; }
.tq-list { display: grid; gap: 16px; min-height: 140px; }
.tq-item { display: flex; gap: 20px; align-items: flex-start; background: #fff; border: 1px solid #e0e8e2; border-radius: 12px; padding: 24px; }
.question-index { flex: none; font-size: 22px; font-family: Georgia, serif; color: #a4b6a8; line-height: 1.3; min-width: 26px; }
.tq-item-main { flex: 1; min-width: 0; }
.tq-item-tags { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 14px; }
.tq-item-tags :deep(.el-tag) { border: 0; border-radius: 5px; font-size: 11px; font-weight: 500; }
.tq-item-content { font-size: 16px; color: #453443; line-height: 1.8; font-weight: 600; white-space: pre-wrap; overflow-wrap: anywhere; margin-bottom: 14px; }
.tq-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; margin-bottom: 16px; }
.tq-options > div { background: #f6f8f5; border-radius: 6px; padding: 10px 12px; color: #78877b; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.tq-item-answer { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; color: #357657; font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
.tq-item-answer span { color: #93a194; font-size: 12px; font-weight: 400; }
.tq-explanation { margin-top: 12px; font-size: 13px; color: #80917f; line-height: 1.8; }
.tq-explanation summary { color: #618167; cursor: pointer; width: fit-content; }
.tq-explanation p { background: #f7faf5; padding: 12px; border-radius: 7px; white-space: pre-wrap; overflow-wrap: anywhere; }
.tq-item-actions { display: flex; flex-direction: column; flex-shrink: 0; padding-left: 12px; border-left: 1px solid #eef2ed; }
.tq-item-actions .el-button { margin-left: 0; }
.edit-dialog-intro { display: flex; gap: 14px; align-items: center; padding: 18px; margin-bottom: 22px; border-radius: 10px; background: #eff6f0; }
.edit-dialog-icon { color: #638b6b; font-size: 26px; }
.edit-dialog-intro strong { color: #42654b; }
.edit-dialog-intro p { font-size: 12px; color: #8a9b8c; margin: 5px 0 0; }
.edit-form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.edit-form-row .el-form-item { min-width: 0; }
.empty-state { padding: 50px 24px; border: 1px dashed #d8e3d8; border-radius: 12px; background: #fafcf9; text-align: center; color: #87988a; }
.empty-symbol { display: grid; place-items: center; width: 48px; height: 48px; margin: 0 auto 16px; border-radius: 14px; background: #eaf1e7; color: #7d9b79; font-size: 26px; }
.empty-state strong { font-size: 17px; color: #577052; }
.empty-state p { font-size: 13px; margin-top: 10px; }
.stats-row { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; padding: 16px 0; border-bottom: 1px solid #e6eee4; font-size: 13px; }
.stats-content { flex: 1; min-width: 150px; overflow-wrap: anywhere; color: #637760; }
.stats-num { color: #8da086; flex-shrink: 0; }
.text-tertiary { padding: 30px; text-align: center; color: #8da086; }
@media(max-width: 700px) { .tq-item { padding: 18px; gap: 12px; flex-wrap: wrap; } .tq-item-main { flex-basis: calc(100% - 48px); } .tq-item-actions { flex-direction: row; border-left: 0; border-top: 1px solid #edf1ec; padding: 8px 0 0; width: 100%; justify-content: flex-end; } .tq-options { grid-template-columns: 1fr; } .tq-toolbar .el-select { width: 100% !important; } .edit-form-row { grid-template-columns: 1fr; } .page-title { font-size: 25px; } }

.tq-toolbar { background: #fffafc; border-color: #eddee5; }
.question-index { color: #b99aa9; }
.tq-options > div { background: #f7f8fb; color: #66738a; }
.tq-item-answer { color: #518879; }
.tq-item-tags :deep(.el-tag--success) { background: #eaf5ef; color: #508671; }
.tq-item-tags :deep(.el-tag--info) { background: #edf2fb; color: #5679ac; }
.tq-item-tags :deep(.el-tag--warning) { background: #fff2dc; color: #b38436; }
.tq-item-tags :deep(.el-tag--danger) { background: #fcebef; color: #b26579; }
.edit-dialog-intro { background: #fff4e8; }
.edit-dialog-intro strong { color: #9b754b; }
.edit-dialog-icon { color: #c79860; }
</style>
