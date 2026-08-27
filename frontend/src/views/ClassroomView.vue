<template>
  <div class="cr">
    <!-- ══════════ 班级列表 ══════════ -->
    <template v-if="!currentCr">
      <header class="cr-header">
        <h1 class="page-title">班级管理</h1>
        <el-button v-if="authStore.isTeacher" type="primary" @click="showCreate=true"><el-icon :size="14"><Plus /></el-icon> 创建班级</el-button>
      </header>

      <div v-if="classrooms.length" class="cr-grid">
        <div v-for="c in classrooms" :key="c.id" class="cr-card" @click="enterClassroom(c)">
          <h3>{{ c.name }}</h3>
          <p class="cr-desc">{{ c.description || '暂无描述' }}</p>
          <div class="cr-meta">
            <span>邀请码: <code>{{ c.invite_code }}</code></span>
            <span>{{ c.member_count }} 名成员</span>
          </div>
          <div class="cr-card-actions" @click.stop>
            <el-button size="small" text type="primary" @click="enterClassroom(c)">进入班级</el-button>
            <el-button v-if="authStore.isTeacher" size="small" text type="danger" @click="deleteCr(c.id)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        暂无班级。
        <span v-if="!authStore.isTeacher">请联系教师获取邀请码加入班级。</span>
      </div>

      <!-- 学生加入班级 -->
      <div v-if="!authStore.isTeacher" class="join-box">
        <div class="join-heading"><span class="join-icon">＋</span><div><h3>加入班级</h3><p>输入教师提供的邀请码加入学习班级</p></div></div>
        <div class="join-actions"><el-input v-model="joinCode" placeholder="输入邀请码" size="small" /><el-button size="small" type="warning" @click="joinClassroom">加入班级</el-button></div>
      </div>
    </template>

    <!-- ══════════ 班级详情 ══════════ -->
    <template v-else>
      <div class="cr-detail-head">
        <button class="back-link" @click="currentCr=null"><el-icon :size="16"><ArrowLeft /></el-icon> 返回班级列表</button>
        <h1 class="page-title">{{ currentCr.name }}</h1>
        <div class="detail-meta">
          <span>邀请码: <code>{{ currentCr.invite_code }}</code></span>
          <span>{{ currentCr.member_count }} 名成员</span>
        </div>
      </div>

      <el-tabs v-model="activeTab">
        <!-- ── 课程 ── -->
        <el-tab-pane label="课程" name="courses">
          <div v-if="authStore.isTeacher" class="inline-form course-link-panel">
            <el-select v-model="linkCourseId" placeholder="选择要关联的课程" size="small" style="width:260px;margin-right:8px" clearable>
              <el-option v-for="c in myCourses" :key="c.id" :label="c.title" :value="c.id" />
            </el-select>
            <el-button size="small" type="primary" @click="linkCourse">关联课程</el-button>
          </div>
          <div v-for="c in linkedCourses" :key="c.id" class="list-item">
            <div class="list-item-head">
              <strong>{{ c.title }}</strong>
              <el-button v-if="authStore.isTeacher" text size="small" type="danger" @click="unlinkCourse(c.id)">取消关联</el-button>
            </div>
            <p class="list-item-body">{{ c.description || '（无描述）' }}</p>
          </div>
          <div v-if="!linkedCourses.length" class="course-empty-card">
            <div class="course-empty-icon">⌘</div>
            <div><strong>还没有关联课程</strong><p>关联课程后，班级成员就能看到课程内容，排名和学习统计也会同步开启。</p></div>
            <el-button v-if="authStore.isTeacher" type="primary" plain @click="linkCourse">立即关联</el-button>
          </div>
        </el-tab-pane>

        <!-- ── 公告 ── -->
        <el-tab-pane label="公告" name="announcements">
          <div v-if="authStore.isTeacher" class="inline-form">
            <el-input v-model="annForm.title" placeholder="公告标题" size="small" style="margin-bottom:6px" />
            <el-input v-model="annForm.content" type="textarea" :rows="2" placeholder="公告内容" size="small" style="margin-bottom:6px" />
            <el-button size="small" type="primary" @click="createAnnouncement">发布公告</el-button>
          </div>
          <div v-for="a in announcements" :key="a.id" class="list-item">
            <div class="list-item-head">
              <strong>{{ a.title }}</strong>
              <span class="meta">{{ a.author }} · {{ a.created_at.slice(0,10) }}</span>
            </div>
            <p class="list-item-body">{{ a.content }}</p>
            <el-button v-if="authStore.isTeacher" text size="small" type="danger" @click="removeAnnouncement(a.id)">删除</el-button>
          </div>
          <div v-if="!announcements.length" class="text-tertiary">暂无公告</div>
        </el-tab-pane>

        <!-- ── 成员 ── -->
        <el-tab-pane label="成员" name="members">
          <div v-if="authStore.isTeacher" class="inline-form">
            <el-input v-model="addMemberName" placeholder="输入学生用户名添加" size="small" style="width:220px;margin-right:8px" />
            <el-button size="small" type="primary" @click="addMember">添加成员</el-button>
          </div>
          <div v-for="m in members" :key="m.id" class="member-row">
            <span>{{ m.username }}</span>
            <el-button v-if="authStore.isTeacher" text size="small" type="danger" @click="removeMember(m.student_id)">移除</el-button>
          </div>
          <div v-if="!members.length" class="text-tertiary">暂无成员</div>
        </el-tab-pane>

        <!-- ── 排名 ── -->
        <el-tab-pane label="排名" name="ranking">
          <div v-for="r in ranking" :key="r.student_id" class="rank-row">
            <span class="rank-badge" :class="{ top1: r.rank===1, top2: r.rank===2, top3: r.rank===3 }">{{ r.rank }}</span>
            <span class="rank-name">{{ r.username }}</span>
            <div class="rank-bar"><div class="rank-bar-fill" :style="{width:(r.average_mastery*100)+'%'}"></div></div>
            <span class="rank-num">{{ Math.round(r.average_mastery*100) }}%</span>
          </div>
          <div v-if="!ranking.length" class="text-tertiary">暂无排名数据（请先关联课程）</div>
        </el-tab-pane>

        <!-- ── 任务 ── -->
        <el-tab-pane label="作业" name="tasks">
          <div v-if="authStore.isTeacher" class="inline-form">
            <div class="form-heading"><div><strong>布置班级作业</strong><span>发布后所有班级成员都可以查看和提交</span></div><el-button size="small" type="warning" @click="$router.push('/practice')">AI 生成题目</el-button></div>
            <el-select v-model="taskCourseId" placeholder="选择作业课程" size="small" style="width:280px;margin-bottom:8px" @change="loadTaskQuestions"><el-option v-for="c in myCourses" :key="c.id" :label="c.title" :value="c.id" /></el-select>
            <div class="question-entry"><el-button size="small" plain :disabled="!taskCourseId" @click="questionDialog=true">选择题目</el-button><span v-if="selectedQuestionIds.length">已选择 {{ selectedQuestionIds.length }} 道题</span><span v-else>请选择需要布置的题目</span></div>
            <el-input v-model="taskForm.title" placeholder="作业标题，例如：Python 基础练习一" size="small" style="margin-bottom:8px" />
            <el-input v-model="taskForm.desc" type="textarea" :rows="2" placeholder="作业要求、截止时间或补充说明" size="small" style="margin-bottom:8px" />
            <el-button size="small" type="primary" @click="createTask">发布作业</el-button>
          </div>
          <el-dialog v-model="questionDialog" title="选择作业题目" width="620px" destroy-on-close>
            <div v-if="taskQuestions.length" class="question-picker"><div class="picker-title"><strong>{{ taskCourseTitle }}</strong><span>已选 {{ selectedQuestionIds.length }} / {{ taskQuestions.length }} 道</span></div><el-checkbox-group v-model="selectedQuestionIds"><el-checkbox v-for="q in taskQuestions" :key="q.id" :value="q.id" class="question-option"><div class="question-detail"><strong>{{ q.content }}</strong><div v-if="q.options?.length" class="question-options">{{ q.options.join('　') }}</div><div class="question-answer">正确答案：{{ q.correct_answer || '未设置' }}</div></div></el-checkbox></el-checkbox-group></div><div v-else class="question-empty">该课程暂无可布置题目，请先使用 AI 生成题目。</div>
            <template #footer><el-button @click="questionDialog=false">取消</el-button><el-button type="primary" @click="questionDialog=false">确认选择</el-button></template>
          </el-dialog>
          <div v-for="t in tasks" :key="t.id" class="task-card">
            <div class="list-item-head">
              <strong>{{ t.title }}</strong>
              <span class="meta">提交 {{ t.submitted_count || 0 }}/{{ t.total_members || 0 }}</span>
            </div>
            <p class="list-item-body">{{ t.description || '（无描述）' }}</p>
            <div v-if="authStore.isTeacher">
              <el-button text size="small" type="primary" @click="viewSubmissions(t)">查看提交</el-button>
            </div>
            <div v-else>
              <el-tag v-if="t.my_submitted" type="success" size="small">已提交</el-tag>
              <div v-else class="student-task-actions"><el-button size="small" type="primary" :disabled="!t.course_id" @click="startTask(t)">开始做题</el-button></div>
            </div>
          </div>
          <div v-if="!tasks.length" class="text-tertiary">暂无作业，教师可以在这里发布班级作业。</div>
        </el-tab-pane>

        <!-- ── 统计 ── -->
        <el-tab-pane label="统计" name="stats">
          <div class="stats-toolbar">
            <span class="meta">平均进度 <strong>{{ Math.round((stats?.average_progress||0)*100) }}%</strong></span>
            <div v-if="authStore.isTeacher" style="display:flex;gap:8px">
              <el-button size="small" @click="exportCsv">导出成绩</el-button>
              <el-button size="small" type="primary" :loading="aiLoading" @click="genAIReport">AI 学情报告</el-button>
            </div>
          </div>
          <div v-for="kp in stats?.knowledge_points || []" :key="kp.knowledge_point_id" class="stats-row">
            <span>{{ kp.name }}</span>
            <div class="stats-bar"><div class="stats-bar-fill" :style="{ width: (kp.mastery_rate * 100) + '%' }"></div></div>
            <span class="stats-num">{{ Math.round(kp.mastery_rate * 100) }}%</span>
          </div>
          <div v-if="stats && !stats.knowledge_points.length" class="text-tertiary">暂无知识点数据（请先关联课程）</div>

          <div v-if="aiReport" class="ai-report" v-html="renderMarkdown(aiReport)"></div>
        </el-tab-pane>

        <!-- ── 讨论区 ── -->
        <el-tab-pane label="讨论区" name="posts">
          <div class="inline-form discussion-composer">
            <div class="composer-heading"><div><strong>发起讨论</strong><span>分享问题、学习心得或课程相关信息</span></div><span class="composer-mark">✦</span></div>
            <div class="composer-fields">
              <el-input v-model="postForm.title" placeholder="给这次讨论起个标题" />
              <el-input v-model="postForm.content" type="textarea" :rows="3" placeholder="写下你的想法，和班级同学一起交流…" />
            </div>
            <div class="composer-footer"><span>内容会展示给班级成员</span><el-button type="primary" @click="createPost">发布讨论</el-button></div>
          </div>
          <div v-for="p in posts" :key="p.id" class="post-card">
            <div class="post-heading">
              <div class="post-avatar">{{ (p.author || '同').slice(0,1) }}</div>
              <div class="post-title-wrap"><strong>{{ p.title }}</strong><span class="meta">{{ p.author }} · {{ p.created_at.slice(0,10) }}</span></div>
            </div>
            <p class="post-content">{{ p.content }}</p>
            <div v-for="cm in p.comments" :key="cm.id" class="comment-row">
              <div class="comment-avatar">{{ (cm.author || '同').slice(0,1) }}</div>
              <div class="comment">
              <span class="comment-author">{{ cm.author }}：</span>{{ cm.content }}
              </div>
            </div>
            <div class="post-actions">
              <el-input v-model="commentDrafts[p.id]" placeholder="回复..." size="small" style="flex:1" />
              <el-button size="small" text type="primary" @click="addComment(p)">回复</el-button>
              <el-button v-if="p.author===authStore.user?.username || authStore.isTeacher" size="small" text type="danger" @click="removePost(p.id)">删除</el-button>
            </div>
          </div>
          <div v-if="!posts.length" class="text-tertiary">暂无讨论</div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 创建班级 -->
    <el-dialog v-model="showCreate" title="创建班级" width="400px">
      <el-input v-model="newCr.name" placeholder="班级名称" style="margin-bottom:8px" />
      <el-input v-model="newCr.desc" placeholder="班级描述" />
      <template #footer>
        <el-button @click="showCreate=false">取消</el-button>
        <el-button type="primary" @click="createClassroom">创建</el-button>
      </template>
    </el-dialog>

    <!-- 查看提交 -->
    <el-dialog v-model="showSubmissions" title="任务提交情况" width="420px">
      <div v-for="s in submissions" :key="s.id" class="member-row">
        <span>{{ s.username }}</span>
        <span class="meta">{{ s.note || '（无备注）' }}</span>
      </div>
      <div v-if="!submissions.length" class="text-tertiary">暂无提交</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { classroomAPI, type Classroom, type ClassroomStats, type ClassroomTask, type RankingItem, type Announcement, type Post } from '@/api/classroom'
import { quizAPI } from '@/api/quiz'
import { coursesAPI } from '@/api/courses'

const authStore = useAuthStore()
const router = useRouter()
const classrooms = ref<Classroom[]>([])
const currentCr = ref<Classroom | null>(null)
const activeTab = ref('courses')

const showCreate = ref(false)
const newCr = ref({ name: '', desc: '' })
const joinCode = ref('')

// 详情数据
const announcements = ref<Announcement[]>([])
const members = ref<any[]>([])
const ranking = ref<RankingItem[]>([])
const tasks = ref<ClassroomTask[]>([])
const stats = ref<ClassroomStats | null>(null)
const posts = ref<Post[]>([])
const linkedCourses = ref<Array<{ id: number; title: string; description: string }>>([])
const myCourses = ref<Array<{ id: number; title: string }>>([])
const linkCourseId = ref<number | undefined>()

// 表单
const annForm = ref({ title: '', content: '' })
const addMemberName = ref('')
const taskForm = ref({ title: '', desc: '' })
const taskCourseId = ref<number>()
const taskQuestions = ref<any[]>([])
const selectedQuestionIds = ref<number[]>([])
const questionDialog = ref(false)
const taskCourseTitle = computed(() => myCourses.value.find(c => c.id === taskCourseId.value)?.title || '待选择课程')
const postForm = ref({ title: '', content: '' })
const commentDrafts = ref<Record<number, string>>({})
const aiReport = ref('')
const aiLoading = ref(false)

const showSubmissions = ref(false)
const submissions = ref<any[]>([])

onMounted(loadClassrooms)

async function loadClassrooms() {
  try { classrooms.value = await classroomAPI.list() } catch { classrooms.value = [] }
}

async function createClassroom() {
  try {
    await classroomAPI.create({ name: newCr.value.name, description: newCr.value.desc })
    showCreate.value = false; newCr.value = { name: '', desc: '' }
    ElMessage.success('班级已创建'); loadClassrooms()
  } catch { /* ignore */ }
}

async function deleteCr(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该班级？', '确认', { type: 'warning' })
    await classroomAPI.remove(id)
    loadClassrooms(); ElMessage.success('已删除')
  } catch { /* cancelled */ }
}

async function joinClassroom() {
  const code = joinCode.value.trim()
  if (!code) { ElMessage.warning('请输入邀请码'); return }
  try {
    await classroomAPI.joinByCode(code)
    ElMessage.success('加入成功'); joinCode.value = ''; loadClassrooms()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '加入失败') }
}

// ── 进入班级 ──
async function enterClassroom(c: Classroom) {
  currentCr.value = c
  activeTab.value = 'courses'
  aiReport.value = ''
  linkCourseId.value = undefined
  await Promise.all([
    loadLinkedCourses(), loadMyCourses(),
    loadAnnouncements(), loadMembers(), loadRanking(), loadTasks(), loadStats(), loadPosts(),
  ])
}

async function loadLinkedCourses() {
  if (!currentCr.value) return
  try { linkedCourses.value = await classroomAPI.courses(currentCr.value.id) } catch { linkedCourses.value = [] }
}

async function loadMyCourses() {
  if (!authStore.isTeacher) { myCourses.value = []; return }
  try { myCourses.value = await coursesAPI.getList() } catch { myCourses.value = [] }
}

async function linkCourse() {
  if (!currentCr.value || !linkCourseId.value) { ElMessage.warning('请选择要关联的课程'); return }
  try {
    await classroomAPI.addCourse(currentCr.value.id, linkCourseId.value)
    ElMessage.success('已关联课程')
    linkCourseId.value = undefined
    loadLinkedCourses()
    loadRanking(); loadStats()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '关联失败') }
}

async function unlinkCourse(courseId: number) {
  if (!currentCr.value) return
  try {
    await classroomAPI.unlinkCourse(currentCr.value.id, courseId)
    ElMessage.success('已取消关联')
    loadLinkedCourses()
    loadRanking(); loadStats()
  } catch { /* ignore */ }
}

async function loadAnnouncements() {
  if (!currentCr.value) return
  try { announcements.value = await classroomAPI.announcements(currentCr.value.id) } catch { announcements.value = [] }
}
async function loadMembers() {
  if (!currentCr.value) return
  try { members.value = await classroomAPI.members(currentCr.value.id) } catch { members.value = [] }
}
async function loadRanking() {
  if (!currentCr.value) return
  try { ranking.value = (await classroomAPI.ranking(currentCr.value.id)).ranking } catch { ranking.value = [] }
}
async function loadTasks() {
  if (!currentCr.value) return
  try { tasks.value = await classroomAPI.tasks(currentCr.value.id) } catch { tasks.value = [] }
}
async function loadStats() {
  if (!currentCr.value) return
  try { stats.value = await classroomAPI.stats(currentCr.value.id) } catch { stats.value = null }
}
async function loadPosts() {
  if (!currentCr.value) return
  try { posts.value = await classroomAPI.posts(currentCr.value.id) } catch { posts.value = [] }
}

async function createAnnouncement() {
  if (!currentCr.value || !annForm.value.title) { ElMessage.warning('请输入公告标题'); return }
  try {
    await classroomAPI.createAnnouncement(currentCr.value.id, annForm.value)
    annForm.value = { title: '', content: '' }
    ElMessage.success('已发布'); loadAnnouncements()
  } catch { /* ignore */ }
}
async function removeAnnouncement(id: number) {
  if (!currentCr.value) return
  try { await classroomAPI.deleteAnnouncement(currentCr.value.id, id); loadAnnouncements() } catch { /* ignore */ }
}

async function addMember() {
  if (!currentCr.value || !addMemberName.value.trim()) { ElMessage.warning('请输入用户名'); return }
  try {
    await classroomAPI.addMember(currentCr.value.id, addMemberName.value.trim())
    addMemberName.value = ''; ElMessage.success('已添加'); loadMembers(); loadClassrooms()
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '添加失败') }
}
async function removeMember(studentId: number) {
  if (!currentCr.value) return
  try {
    await ElMessageBox.confirm('确定移除该成员？', '确认', { type: 'warning' })
    await classroomAPI.removeMember(currentCr.value.id, studentId)
    ElMessage.success('已移除'); loadMembers(); loadClassrooms()
  } catch { /* cancelled */ }
}

async function createTask() {
  if (!currentCr.value || !taskForm.value.title) { ElMessage.warning('请输入作业标题'); return }
  try {
    await classroomAPI.createTask(currentCr.value.id, { title: taskForm.value.title, description: taskForm.value.desc, course_id: taskCourseId.value })
    taskForm.value = { title: '', desc: '' }; taskCourseId.value = undefined; taskQuestions.value = []; selectedQuestionIds.value = []
    ElMessage.success('任务已布置'); loadTasks()
  } catch { /* ignore */ }
}

async function loadTaskQuestions() {
  selectedQuestionIds.value = []
  taskQuestions.value = taskCourseId.value ? await quizAPI.listQuestions(taskCourseId.value) : []
}
function startTask(t: ClassroomTask) {
  if (t.course_id) router.push(`/course/${t.course_id}/practice`)
}

async function viewSubmissions(t: ClassroomTask) {
  if (!currentCr.value) return
  try {
    submissions.value = await classroomAPI.taskSubmissions(currentCr.value.id, t.id)
    showSubmissions.value = true
  } catch { /* ignore */ }
}

function exportCsv() {
  if (!currentCr.value) return
  classroomAPI.exportCsv(currentCr.value.id).then((r) => {
    const blob = new Blob([r.csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = r.filename; a.click()
    URL.revokeObjectURL(url)
  }).catch(() => ElMessage.error('导出失败'))
}

async function genAIReport() {
  if (!currentCr.value) return
  aiLoading.value = true
  try {
    const r = await classroomAPI.aiReport(currentCr.value.id)
    aiReport.value = r.report
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '生成失败') } finally { aiLoading.value = false }
}

async function createPost() {
  if (!currentCr.value || !postForm.value.title) { ElMessage.warning('请输入帖子标题'); return }
  try {
    await classroomAPI.createPost(currentCr.value.id, postForm.value)
    postForm.value = { title: '', content: '' }
    ElMessage.success('已发帖'); loadPosts()
  } catch { /* ignore */ }
}
async function addComment(p: Post) {
  if (!currentCr.value) return
  const content = (commentDrafts.value[p.id] || '').trim()
  if (!content) { ElMessage.warning('请输入回复内容'); return }
  try {
    await classroomAPI.createComment(currentCr.value.id, p.id, content)
    commentDrafts.value[p.id] = ''
    loadPosts()
  } catch { /* ignore */ }
}
async function removePost(postId: number) {
  if (!currentCr.value) return
  try {
    await classroomAPI.deletePost(currentCr.value.id, postId)
    ElMessage.success('已删除'); loadPosts()
  } catch { /* ignore */ }
}

function renderMarkdown(text: string): string {
  if (!text) return ''
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n### (.+)/g, '<h4>$1</h4>')
    .replace(/\n- (.+)/g, '<li>$1</li>')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped>
.cr { max-width: 1000px; margin: 0 auto; }
.cr-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; margin: 0; }
.cr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.cr-card { background: #fff; border: 1.5px solid #93c5fd; border-radius: 12px; padding: 20px; cursor: pointer; transition: all .15s; }
.cr-card:hover { border-color: #60a5fa; box-shadow: 0 4px 12px rgba(37,99,235,.12); transform: translateY(-1px); }
.cr-card h3 { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.cr-desc { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.cr-meta { display: flex; gap: 16px; font-size: 12px; color: #94a3b8; }
.cr-meta code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }
.cr-card-actions { display: flex; justify-content: flex-end; margin-top: 12px; }
.empty-state { text-align: center; padding: 60px; color: #94a3b8; }
.join-box { margin-top: 24px; padding: 20px; background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0; max-width: 400px; }
.join-box h3 { margin-bottom: 12px; }

.cr-detail-head { margin-bottom: 16px; }
.back-link { display: inline-flex; align-items: center; gap: 4px; border: none; background: none; color: #64748b; cursor: pointer; margin-bottom: 12px; font-family: inherit; }
.detail-meta { display: flex; gap: 16px; font-size: 13px; color: #64748b; margin-top: 8px; }
.detail-meta code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; }

.inline-form { padding: 12px; background: #f8fafc; border-radius: 8px; margin-bottom: 12px; }
.list-item { padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; }
.list-item-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.list-item-head strong { font-size: 14px; }
.list-item-body { font-size: 13px; color: #475569; margin: 0; }
.meta { font-size: 12px; color: #94a3b8; }
.member-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
.text-tertiary { color: #94a3b8; font-size: 13px; padding: 12px 0; }

.rank-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.rank-badge { width: 26px; height: 26px; border-radius: 50%; background: #e2e8f0; color: #475569; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }
.rank-badge.top1 { background: #fde68a; color: #b45309; }
.rank-badge.top2 { background: #e2e8f0; color: #64748b; }
.rank-badge.top3 { background: #fed7aa; color: #c2410c; }
.rank-name { width: 100px; flex-shrink: 0; font-size: 14px; }
.rank-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.rank-bar-fill { height: 100%; background: linear-gradient(90deg, #60a5fa, #2563eb); border-radius: 4px; }
.rank-num { width: 46px; text-align: right; font-size: 13px; color: #2563eb; font-weight: 600; }

.task-card { padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; }
.stats-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.cr-detail-head { background:linear-gradient(135deg,#ffffff,#f7fbff); border:1px solid #dbe5f0; border-radius:18px; padding:24px 28px; box-shadow:0 8px 22px rgba(30,64,175,.06); }
.cr-detail-head .page-title { margin:14px 0 8px; color:#172554; }
.detail-meta { color:#64748b; }
.cr :deep(.el-tabs__header) { margin:24px 0 0; border-bottom:1px solid #dbe5f0; }
.cr :deep(.el-tabs__item) { color:#64748b; font-weight:600; }
.cr :deep(.el-tabs__item.is-active) { color:#16a34a; }
.cr :deep(.el-tabs__active-bar) { background:#16a34a; height:3px; border-radius:3px; }
.cr :deep(.el-tab-pane) { padding:20px 0; }
.inline-form { background:#f1f7ff; border:1px solid #dbeafe; border-radius:14px; padding:18px; margin-bottom:18px; }
.course-empty-card { display:flex; align-items:center; gap:16px; padding:24px; border:1px dashed #93c5fd; border-radius:16px; background:#f8fbff; color:#334155; }
.course-empty-icon { display:grid; place-items:center; width:46px; height:46px; flex:none; border-radius:14px; background:#dbeafe; color:#2563eb; font-size:25px; font-weight:700; }
.course-empty-card strong { color:#1e3a8a; font-size:16px; }
.course-empty-card p { margin:6px 0 0; color:#64748b; font-size:13px; }
.course-empty-card .el-button { margin-left:auto; flex:none; }
.cr .list-item { position:relative; padding:22px 24px; border:1px solid #c7d8ee; border-left:5px solid #2563eb; border-radius:16px; background:linear-gradient(135deg,#f8fbff,#eef5ff); box-shadow:0 5px 14px rgba(37,99,235,.08); }
.cr .list-item-head strong { color:#1e3a8a; font-size:18px; }
.cr .list-item-body { margin:10px 0 0; color:#64748b; }
.cr .list-item-head .el-button { color:#dc2626; }
.cr .course-link-panel { display:flex; align-items:center; gap:10px; padding:14px 16px; margin-bottom:18px; background:#fff; border:1px solid #e2e8f0; border-radius:14px; box-shadow:0 3px 10px rgba(15,23,42,.04); }
.cr .course-link-panel:before { content:'关联课程'; color:#334155; font-size:13px; font-weight:700; white-space:nowrap; }
.cr .course-link-panel .el-select { width:280px !important; margin-right:0 !important; }
.cr .course-link-panel .el-button { margin-left:0; box-shadow:none; }
.cr .inline-form { background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:16px 18px; margin-bottom:18px; box-shadow:0 3px 10px rgba(15,23,42,.04); }
.cr .inline-form:not(.course-link-panel) { display:block; }
.cr .inline-form .el-input,.cr .inline-form .el-select { max-width:100%; }
.cr .inline-form .el-button { box-shadow:none; }
.cr .inline-form + .list-item,.cr .inline-form + .member-row,.cr .inline-form + .task-card { margin-top:0; }
.cr .stats-toolbar { padding:14px 16px; border:1px solid #e2e8f0; border-radius:14px; background:#fff; box-shadow:0 3px 10px rgba(15,23,42,.04); }
.cr .post-actions { padding:12px; margin-top:14px; border-radius:12px; background:#f8fafc; }
.question-picker{max-height:220px;overflow:auto;padding:12px 14px;margin:0 0 10px;border:1px solid #dbeafe;border-radius:12px;background:#f8fbff}.picker-title{display:flex;justify-content:space-between;margin-bottom:8px;color:#1e3a8a;font-size:13px}.picker-title span{color:#64748b;font-size:12px}.question-option{display:flex!important;width:100%;margin:0!important;padding:8px 0;border-bottom:1px solid #e5edf7}.question-option:last-child{border-bottom:0}.question-option :deep(.el-checkbox__label){white-space:normal;line-height:1.5;color:#475569}.question-empty{padding:12px;margin-bottom:10px;border-radius:10px;background:#fff7ed;color:#c2410c;font-size:12px}
.cr .list-item { display:flex; align-items:center; gap:18px; min-height:86px; padding:18px 22px; border-left:0; border-top:4px solid #3b82f6; background:#fff; box-shadow:0 4px 14px rgba(30,64,175,.07); }
.cr .list-item:before { content:'课'; display:grid; place-items:center; width:46px; height:46px; flex:none; border-radius:14px; background:#dbeafe; color:#1d4ed8; font-weight:800; }
.cr .list-item-head { flex:1; min-width:0; }
.cr .list-item-head strong { display:block; font-size:17px; }
.cr .list-item-body { margin:6px 0 0; }
.form-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:14px}.form-heading strong{display:block;color:#1e3a8a;font-size:16px}.form-heading span{display:block;margin-top:4px;color:#64748b;font-size:12px}.form-heading .el-button{flex:none}.cr :deep(.el-input__wrapper),.cr :deep(.el-textarea__inner),.cr :deep(.el-select__wrapper){border-radius:10px;box-shadow:0 0 0 1px #dbe5f0 inset}.cr :deep(.el-input__wrapper:hover),.cr :deep(.el-textarea__inner:hover){box-shadow:0 0 0 1px #93c5fd inset}.cr .task-card{padding:20px;border-left:4px solid #f59e0b;background:#fffaf0}.cr .task-card strong{color:#92400e;font-size:16px}.cr .post-card{padding:20px;background:#fff}.cr .member-row,.cr .rank-row,.cr .stats-row{padding:14px 16px;border-radius:10px;background:#f8fbff;margin-bottom:8px}.cr .text-tertiary{padding:30px 20px;text-align:center;color:#94a3b8;background:#f8fafc;border-radius:12px}
.stats-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
.stats-row > span:first-child { width: 120px; flex-shrink: 0; }
.stats-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.stats-bar-fill { height: 100%; background: linear-gradient(90deg, #60a5fa, #2563eb); border-radius: 4px; }
.stats-num { width: 40px; text-align: right; color: #2563eb; font-weight: 600; flex-shrink: 0; }
.ai-report { margin-top: 16px; padding: 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; line-height: 1.7; font-size: 13px; }
.ai-report :deep(h4) { margin: 8px 0 4px; }
.ai-report :deep(li) { margin-left: 16px; }

.post-card { padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; }
.comment { background: #f8fafc; padding: 6px 10px; border-radius: 6px; font-size: 13px; margin: 6px 0; }
.comment-author { color: #2563eb; font-weight: 600; }
.post-actions { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
.cr{max-width:1180px}.cr-header{padding:4px 2px 20px}.cr-grid{gap:18px}.cr-card,.join-box,.cr-detail-head,.list-item,.task-card,.post-card{border:1px solid #e4e8e2;border-radius:16px;background:#fff;box-shadow:0 3px 12px rgba(15,23,42,.04)}.cr-card:nth-child(4n+1){border-top:4px solid #3b82f6}.cr-card:nth-child(4n+2){border-top:4px solid #f59e0b}.cr-card:nth-child(4n+3){border-top:4px solid #22c55e}.cr-card:nth-child(4n){border-top:4px solid #8b5cf6}.join-box{background:#eff6ff;border-color:#bfdbfe}.list-item:nth-child(3n){background:#fffaf4}.list-item:nth-child(3n+1){background:#f5fcf7}.list-item:nth-child(3n+2){background:#f5f9ff}.empty-state{border:1px dashed #cbd5e1;border-radius:16px;background:#fbfcfa}
.question-entry{display:flex;align-items:center;gap:10px;padding:10px 12px;margin-bottom:10px;border:1px dashed #cbd5e1;border-radius:10px;background:#f8fafc;color:#94a3b8;font-size:12px}.question-entry span:first-of-type{color:#2563eb;font-weight:600}.question-picker{max-height:300px;overflow:auto;padding:12px 14px;border:1px solid #dbeafe;border-radius:12px;background:#f8fbff}.picker-title{display:flex;justify-content:space-between;margin-bottom:8px;color:#1e3a8a;font-size:13px}.question-option{display:flex!important;width:100%;margin:0!important;padding:8px 0;border-bottom:1px solid #e5edf7}.question-option :deep(.el-checkbox__label){white-space:normal;line-height:1.5}.question-empty{padding:12px;border-radius:10px;background:#fff7ed;color:#c2410c;font-size:12px}
.question-detail{display:block;padding-left:4px}.question-detail strong{display:block;color:#334155;font-size:13px;line-height:1.5}.question-options{margin-top:5px;color:#64748b;font-size:12px;line-height:1.6}.question-answer{margin-top:4px;color:#16a34a;font-size:12px;font-weight:600}
.question-option{align-items:flex-start!important;height:auto!important;line-height:1.5!important}.question-option :deep(.el-checkbox__input){margin-top:3px;flex:none}.question-option :deep(.el-checkbox__label){display:block!important;padding-left:8px!important;overflow:visible!important}
.cr .join-box{max-width:520px;padding:22px 24px;margin-top:20px;border:1px solid #fed7aa;border-left:5px solid #f97316;border-radius:16px;background:#fffaf5;box-shadow:0 6px 18px rgba(234,88,12,.08)}.join-heading{display:flex;align-items:center;gap:12px;margin-bottom:18px}.join-icon{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:#ffedd5;color:#ea580c;font-size:26px}.join-heading h3{margin:0;color:#9a3412;font-size:18px}.join-heading p{margin:4px 0 0;color:#9a3412;font-size:12px;opacity:.72}.join-actions{display:flex;gap:10px;align-items:center}.join-actions .el-input{flex:1}.join-actions .el-button{flex:none;box-shadow:0 5px 12px rgba(234,88,12,.18)}
.cr .post-card{border:1px solid #ddd6fe;border-top:4px solid #8b5cf6;background:#fff;box-shadow:0 6px 16px rgba(124,58,237,.08)}.cr .post-card:nth-of-type(odd){border-top-color:#f97316}.cr .post-card .list-item-head strong{color:#4c1d95;font-size:17px}.cr .post-card .meta{color:#a78bfa}.cr .post-card .list-item-body{color:#475569;line-height:1.7}.cr .post-actions{background:#faf5ff;border:1px solid #ede9fe}.cr .post-actions .el-button{color:#7c3aed}.cr .post-actions .el-button[type="danger"]{color:#dc2626}.cr .comment{background:#fff7ed;border-left:3px solid #fb923c;color:#57534e;padding:9px 12px}.cr .comment-author{color:#c2410c}.cr .inline-form:has(+ .post-card){background:linear-gradient(135deg,#faf5ff,#fff7ed);border-color:#ddd6fe;border-left:4px solid #8b5cf6}
.student-task-actions{display:flex;gap:8px;align-items:center}
.cr{max-width:1220px;padding:8px 4px 40px;color:#334155}.cr-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px;padding:0}.cr-header .page-title{font-size:30px;color:#172554}.cr-header .el-button{border-radius:11px;padding:11px 18px;box-shadow:0 6px 14px rgba(34,197,94,.16)}.cr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}.cr-card{position:relative;min-height:190px;padding:22px;overflow:hidden;border:1px solid #e2e8f0;border-radius:18px;background:#fff;box-shadow:0 7px 20px rgba(15,23,42,.06);cursor:pointer;transition:transform .2s,box-shadow .2s}.cr-card:hover{transform:translateY(-3px);box-shadow:0 14px 28px rgba(15,23,42,.11)}.cr-card h3{margin:0 0 10px;color:#172554;font-size:19px}.cr-desc{min-height:40px;color:#64748b;line-height:1.6}.cr-meta{display:flex;justify-content:space-between;gap:10px;padding-top:16px;margin-top:18px;border-top:1px solid #eef2f7;color:#94a3b8;font-size:12px}.cr-meta code{padding:3px 7px;border-radius:6px;background:#eff6ff;color:#2563eb}.cr-card-actions{display:flex;justify-content:flex-end;margin-top:10px}.cr-detail-head{margin-bottom:20px;padding:24px 28px;border:1px solid #e2e8f0;border-radius:20px;background:linear-gradient(135deg,#fff,#f7fbff);box-shadow:0 8px 22px rgba(30,64,175,.07)}.cr-detail-head .page-title{margin:14px 0 8px;color:#172554;font-size:28px}.cr :deep(.el-tabs__header){margin:0;padding:0 4px;border-bottom:1px solid #e2e8f0}.cr :deep(.el-tabs__nav-wrap:after){background:#eef2f7}.cr :deep(.el-tabs__item){height:52px;color:#64748b;font-size:15px;font-weight:600}.cr :deep(.el-tabs__item.is-active){color:#2563eb}.cr :deep(.el-tabs__active-bar){height:3px;border-radius:3px;background:#2563eb}.cr :deep(.el-tab-pane){padding:22px 0}.cr .member-row,.cr .rank-row,.cr .stats-row{border:1px solid #e2e8f0;border-radius:14px;background:#fff;box-shadow:0 3px 10px rgba(15,23,42,.04)}.cr .post-card{margin-bottom:14px;padding:22px;border-radius:17px}.cr .post-actions{display:flex;align-items:center;gap:8px}.cr .empty-state{padding:52px 24px;border:1px dashed #c4b5fd;background:#faf5ff;color:#7c3aed;text-align:center}.cr .task-card{margin-bottom:14px;border-left:4px solid #f59e0b}.cr .ai-report{border-left:4px solid #8b5cf6;background:#faf5ff}@media(max-width:700px){.cr-header{align-items:flex-start;gap:12px}.cr-header .page-title{font-size:24px}.cr-detail-head{padding:20px}.cr :deep(.el-tabs__item){padding:0 10px;font-size:13px}.cr .post-actions{flex-wrap:wrap}.cr .post-actions .el-input{min-width:100%}}
.discussion-composer{padding:20px 22px!important;border:1px solid #dbeafe!important;border-left:4px solid #2563eb!important;border-radius:16px!important;background:#f8fbff!important;box-shadow:0 6px 18px rgba(37,99,235,.06)!important}.composer-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.composer-heading strong{display:block;color:#1e3a8a;font-size:17px}.composer-heading span:not(.composer-mark){display:block;margin-top:4px;color:#64748b;font-size:12px}.composer-mark{color:#2563eb;font-size:24px}.composer-fields{display:grid;gap:10px}.composer-footer{display:flex;align-items:center;justify-content:space-between;margin-top:14px;color:#94a3b8;font-size:12px}.composer-footer .el-button{border-radius:10px}.cr .post-card{padding:18px 20px!important;border:1px solid #e2e8f0!important;border-top:3px solid #8b5cf6!important;border-radius:15px!important;background:#fff!important;box-shadow:0 5px 16px rgba(15,23,42,.05)!important}.cr .post-card:nth-of-type(odd){border-top-color:#f59e0b!important}.post-heading{display:flex;align-items:center;gap:11px}.post-avatar,.comment-avatar{display:grid;place-items:center;flex:none;border-radius:10px;background:#ede9fe;color:#6d28d9;font-weight:700}.post-avatar{width:36px;height:36px}.comment-avatar{width:25px;height:25px;border-radius:8px;background:#ffedd5;color:#c2410c;font-size:12px}.post-title-wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;min-width:0;flex:1}.post-title-wrap strong{color:#1e293b;font-size:17px}.post-title-wrap .meta{color:#94a3b8;font-size:12px;white-space:nowrap}.post-content{margin:16px 0 18px;padding-left:47px;color:#475569;line-height:1.7}.comment-row{display:flex;align-items:flex-start;gap:8px;margin:7px 0 0 47px}.cr .comment{flex:1;margin:0;padding:8px 11px;border:0;border-radius:9px;background:#f8fafc;color:#64748b}.cr .post-actions{margin:14px 0 0 47px;padding:10px 0 0;border:0;border-top:1px solid #eef2f7;background:transparent}.cr .post-actions .el-input{flex:1}.cr .text-tertiary{padding:42px 20px;border:1px dashed #cbd5e1;border-radius:15px;background:#f8fafc;color:#94a3b8;text-align:center}
</style>
