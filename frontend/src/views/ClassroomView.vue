<template>
  <div class="cr">
    <!-- ══════════ 班级列表 ══════════ -->
    <template v-if="!currentCr">
      <header class="cr-header">
        <div><span class="section-kicker">一起学习 · 共同进步</span><h1 class="page-title">我的班级</h1><p class="header-caption">让课程、作业与每一次交流，在这里连接。</p></div>
        <el-button v-if="authStore.isTeacher" type="primary" @click="showCreate=true"><el-icon :size="14"><Plus /></el-icon> 创建班级</el-button>
      </header>

      <div v-if="classrooms.length" class="cr-grid">
        <div v-for="c in classrooms" :key="c.id" class="cr-card" tabindex="0" @keydown.enter.self="enterClassroom(c)" @click="enterClassroom(c)">
          <span class="class-monogram">{{ c.name.slice(0, 1) }}</span><h3>{{ c.name }}</h3>
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
        <span class="section-kicker">班级学习空间</span><h1 class="page-title">{{ currentCr.name }}</h1><p v-if="currentCr.description" class="header-caption">{{ currentCr.description }}</p>
        <div class="detail-meta">
          <span>邀请码: <code>{{ currentCr.invite_code }}</code></span>
          <span>{{ currentCr.member_count }} 名成员</span>
        </div>
        <div class="class-summary"><span><b>{{ linkedCourses.length }}</b> 关联课程</span><span><b>{{ tasks.length }}</b> 班级作业</span><span><b>{{ posts.length }}</b> 交流话题</span></div>
      </div>

      <el-tabs v-model="activeTab">
        <!-- ── 课程 ── -->
        <el-tab-pane label="课程" name="courses">
          <div v-if="authStore.isTeacher" class="inline-form course-link-panel">
            <div class="panel-intro"><strong>把课程带进班级</strong><p>关联后，成员即可共同学习课程内容</p></div>
            <el-select v-model="linkCourseId" placeholder="选择要关联的课程" size="small" style="width:260px;margin-right:8px" clearable>
              <el-option v-for="c in myCourses" :key="c.id" :label="c.title" :value="c.id" />
            </el-select>
            <el-button size="small" type="primary" @click="linkCourse">关联课程</el-button>
          </div>
          <div v-for="c in linkedCourses" :key="c.id" class="list-item course-card">
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
            <div class="panel-intro"><strong>发布班级公告</strong><p>让重要通知及时传达给每一位同学</p></div>
            <el-input v-model="annForm.title" placeholder="公告标题" size="small" style="margin-bottom:6px" />
            <el-input v-model="annForm.content" type="textarea" :rows="2" placeholder="公告内容" size="small" style="margin-bottom:6px" />
            <el-button size="small" type="primary" @click="createAnnouncement">发布公告</el-button>
          </div>
          <div v-for="a in announcements" :key="a.id" class="list-item announcement-card">
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
          <div v-if="authStore.isTeacher" class="inline-form member-form">
            <div class="panel-intro"><strong>邀请同学加入</strong><p>通过用户名添加成员，也可以分享班级邀请码</p></div>
            <el-input v-model="addMemberName" placeholder="输入学生用户名添加" size="small" style="width:220px;margin-right:8px" />
            <el-button size="small" type="primary" @click="addMember">添加成员</el-button>
          </div>
          <div v-for="m in members" :key="m.id" class="member-row">
            <span class="member-identity"><span class="member-avatar">{{ m.username.slice(0,1) }}</span>{{ m.username }}</span>
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
          <el-dialog v-model="questionDialog" title="选择作业题目" width="min(720px, 94vw)" destroy-on-close>
            <div v-if="taskQuestions.length" class="question-picker"><div class="picker-title"><strong>{{ taskCourseTitle }}</strong><span>已选 {{ selectedQuestionIds.length }} / {{ taskQuestions.length }} 道</span></div><el-checkbox-group v-model="selectedQuestionIds"><el-checkbox v-for="q in taskQuestions" :key="q.id" :value="q.id" class="question-option"><div class="question-detail"><strong>{{ q.content }}</strong><div v-if="q.options?.length" class="question-options"><div v-for="(option, index) in q.options" :key="index">{{ option }}</div></div><div class="question-answer">正确答案：{{ q.correct_answer || '未设置' }}</div></div></el-checkbox></el-checkbox-group></div><div v-else class="question-empty">该课程暂无可布置题目，请先使用 AI 生成题目。</div>
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

          <div v-if="aiReport" class="ai-report" v-html="safeHTML(renderMarkdown(aiReport))"></div>
        </el-tab-pane>

        <!-- ── 讨论区 ── -->
        <el-tab-pane label="讨论区" name="posts">
          <div class="discussion-intro"><div><span class="section-kicker">班级交流空间</span><h2>好问题，值得一起讨论。</h2></div><div class="discussion-tools"><span class="topic-count">{{ posts.length }} 个话题</span><el-button type="primary" @click="composerOpen = !composerOpen">{{ composerOpen ? '收起编辑' : '发起讨论' }}</el-button></div></div>
          <div v-show="composerOpen" class="inline-form discussion-composer">
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
    <el-dialog v-model="showCreate" title="创建班级" width="min(440px, 94vw)">
      <el-input v-model="newCr.name" placeholder="班级名称" style="margin-bottom:8px" />
      <el-input v-model="newCr.desc" placeholder="班级描述" />
      <template #footer>
        <el-button @click="showCreate=false">取消</el-button>
        <el-button type="primary" @click="createClassroom">创建</el-button>
      </template>
    </el-dialog>

    <!-- 查看提交 -->
    <el-dialog v-model="showSubmissions" title="作业提交情况" width="min(480px, 94vw)">
      <div v-for="s in submissions" :key="s.id" class="member-row">
        <span>{{ s.username }}</span>
        <span class="meta">{{ s.note || '（无备注）' }}</span>
      </div>
      <div v-if="!submissions.length" class="text-tertiary">暂无提交</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { safeHTML } from "@/utils/safeHtml"
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
const composerOpen = ref(false)
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
  if (taskCourseId.value && !selectedQuestionIds.value.length) { ElMessage.warning('请至少选择一道题目'); return }
  try {
    await classroomAPI.createTask(currentCr.value.id, { title: taskForm.value.title, description: taskForm.value.desc, course_id: taskCourseId.value, question_ids: selectedQuestionIds.value })
    taskForm.value = { title: '', desc: '' }; taskCourseId.value = undefined; taskQuestions.value = []; selectedQuestionIds.value = []
    ElMessage.success('任务已布置'); loadTasks()
  } catch { /* ignore */ }
}

async function loadTaskQuestions() {
  selectedQuestionIds.value = []
  taskQuestions.value = taskCourseId.value ? await quizAPI.listQuestions(taskCourseId.value) : []
}
async function startTask(t: ClassroomTask) {
  if (!t.course_id || !currentCr.value) return
  try {
    const session = await classroomAPI.startTask(currentCr.value.id, t.id)
    router.push(`/course/${t.course_id}/practice?session=${session.session_id}&classroom=${currentCr.value.id}&task=${t.id}`)
  } catch { /* API 层已提示 */ }
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
    composerOpen.value = false
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
.cr {
  --class-accent: #7150bc;
  --class-border: #e1e8e6;
  --el-color-primary: #456fc2;
  --el-color-primary-light-3: #6c8ed0;
  --el-color-primary-light-5: #95addc;
  --el-color-primary-light-7: #c4d3ed;
  --el-color-primary-light-8: #dce5f6;
  --el-color-primary-light-9: #eff4fc;
  --el-color-primary-dark-2: #34579c;
  max-width: 1160px; margin: 0 auto; padding: 8px 0 40px;
  color: #253b38; font-size: 14px; line-height: 1.6;
}
.cr *, .cr :deep(*) { box-sizing: border-box; }
.section-kicker { display: block; color: var(--class-accent); font-size: 12px; font-weight: 700; letter-spacing: 2px; }
.page-title { margin: 6px 0; font-size: 30px; line-height: 1.35; font-weight: 750; letter-spacing: -.7px; color: #263b5c; overflow-wrap: anywhere; }
.header-caption { margin: 8px 0 0; color: #73847f; font-size: 14px; overflow-wrap: anywhere; }
.cr-header { display: flex; align-items: center; justify-content: space-between; flex-wrap:wrap; gap:20px; padding:26px; margin-bottom:24px; border-radius:18px; background:linear-gradient(110deg,#ebe3fb,#f6f1ff 65%,#ffeede); border:1px solid #ded3f1; }
.cr :deep(.el-button) { border-radius: 8px; box-shadow: none; font-weight: 600; }
.cr :deep(.el-button--small) { min-height: 34px; padding: 8px 13px; }
.cr :deep(.el-button--primary:not(.is-text):not(.is-plain)) { background: var(--class-accent); border-color: var(--class-accent); }
.cr :deep(.el-button--primary:not(.is-text):hover) { filter: brightness(.95); }
.cr :deep(.el-input__wrapper), .cr :deep(.el-select__wrapper) { min-height: 40px; border-radius: 8px; background: #fff; box-shadow: 0 0 0 1px #dbe5e1 inset; }
.cr :deep(.el-textarea__inner) { padding: 12px 14px; border-radius: 8px; min-height: 100px; box-shadow: 0 0 0 1px #dbe5e1 inset; line-height: 1.7; }
.cr :deep(.el-input__wrapper.is-focus), .cr :deep(.el-select__wrapper.is-focused), .cr :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px var(--class-accent) inset, 0 0 0 3px #e5f3ee; }
.cr :deep(input::placeholder), .cr :deep(textarea::placeholder) { color: #91a19b; }
.cr :deep(.el-select__placeholder.is-transparent) { color: #91a19b; }
.cr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(290px, 100%), 1fr)); gap: 20px; }
.cr-card { padding: 24px; border: 1px solid var(--class-border); border-radius: 16px; background: #fff; cursor: pointer; transition: transform .18s, box-shadow .18s; }
.cr-card:hover { transform: translateY(-3px); box-shadow: 0 10px 25px #173f3310; }
.cr-card:focus-visible { outline: 2px solid var(--class-accent); outline-offset: 3px; }
.class-monogram { display: grid; place-items: center; width: 48px; height: 48px; border-radius: 13px; background: #e3f2ed; color: #456fc2; font-size: 22px; font-weight: 700; margin-bottom: 20px; }
.cr-card:nth-child(3n+2) .class-monogram { background: #fff0d6; color: #9d6d20; }
.cr-card:nth-child(3n) .class-monogram { background: #e7effc; color: #436ca9; }
.cr-card h3 { margin: 0; font-size: 20px; overflow-wrap: anywhere; }
.cr-desc { min-height: 44px; color: #7b8984; margin: 10px 0 20px; overflow-wrap: anywhere; }
.cr-meta { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; border-top: 1px solid #edf1ef; padding-top: 16px; font-size: 12px; color: #73847f; }
.cr code { font-family: ui-monospace, monospace; letter-spacing: 1px; background: #edf5f2; color: #287366; padding: 3px 7px; border-radius: 5px; }
.cr-card-actions { display: flex; justify-content: space-between; padding-top: 14px; }
.cr-detail-head { padding: 24px 28px 0; background: #fff; border: 1px solid var(--class-border); border-radius: 16px; margin-bottom: 22px; }
.back-link { display: inline-flex; align-items: center; gap: 6px; padding: 0; margin-bottom: 22px; border: 0; background: transparent; color: #70857c; font: inherit; font-size: 12px; cursor: pointer; }
.back-link:hover { color: var(--class-accent); }
.detail-meta { display: flex; flex-wrap: wrap; gap: 20px; color: #73847f; margin-top: 14px; font-size: 13px; }
.class-summary { display: flex; flex-wrap: wrap; gap: 36px; margin-top: 24px; border-top: 1px solid #edf1ef; padding: 18px 0; }
.class-summary span { display: flex; align-items: baseline; gap: 9px; color: #819089; font-size: 12px; }
.class-summary b { font-size: 24px; font-weight: 650; color: #365d50; line-height: 1; }
.cr :deep(.el-tabs__header) { margin: 0; }
.cr :deep(.el-tabs__nav-wrap::after) { height: 1px; background: var(--class-border); }
.cr :deep(.el-tabs__item) { height: 50px; font-size: 14px; font-weight: 600; color: #77877e; }
.cr :deep(.el-tabs__item.is-active) { color: var(--class-accent); }
.cr :deep(.el-tabs__active-bar) { height: 3px; background: var(--class-accent); border-radius: 3px; }
.cr :deep(.el-tab-pane) { padding: 24px 0 0; }
.inline-form { background: #fff; border: 1px solid var(--class-border); border-radius: 12px; padding: 22px; margin-bottom: 24px; }
.panel-intro strong, .form-heading strong, .composer-heading strong { display: block; font-size: 16px; color: #304d43; font-weight: 650; }
.panel-intro p, .form-heading span, .composer-heading span:not(.composer-mark) { display: block; margin: 4px 0 16px; font-size: 12px; color: #85958d; }
.course-link-panel, .member-form { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; background: #f0f6f2; }
.course-link-panel .panel-intro, .member-form .panel-intro { flex: 1; min-width: 220px; }
.course-link-panel .panel-intro p, .member-form .panel-intro p { margin-bottom: 0; }
.inline-form .el-input, .inline-form .el-select { max-width: 100%; }
.course-link-panel .el-select, .member-form .el-input { margin-right: 0 !important; }
.list-item, .task-card { background: #fff; border: 1px solid var(--class-border); border-radius: 12px; padding: 22px; margin-bottom: 14px; }
.list-item-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.list-item-head strong { font-size: 17px; color: #30443c; overflow-wrap: anywhere; }
.list-item-body { margin: 12px 0 0; font-size: 14px; line-height: 1.8; color: #78867e; white-space: pre-wrap; overflow-wrap: anywhere; }
.course-card { position: relative; padding-left: 80px; }
.course-card::before { content: '课'; position: absolute; left: 22px; top: 24px; width: 40px; height: 44px; display: grid; place-items: center; border-radius: 7px; background: #eaf2fb; color: #49729e; font-size: 18px; font-weight: 700; }
.announcement-card { border-left: 3px solid #d6b76e; }
.meta { font-size: 12px; color: #8a9991; }
.form-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 15px; }
.question-entry { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; background: #f5f8f6; border: 1px dashed #cdded5; border-radius: 8px; padding: 12px; margin-bottom: 12px; font-size: 12px; color: #73857b; }
.task-card .list-item-head .meta { padding: 4px 10px; border-radius: 6px; background: #faf3e7; color: #9a7840; }
.task-card > div:last-child { margin-top: 14px; }
.student-task-actions { display: flex; align-items: center; gap: 10px; }
.member-row, .rank-row, .stats-row { display: flex; align-items: center; gap: 18px; padding: 16px 20px; background: #fff; border-bottom: 1px solid #edf1ee; }
.member-row { justify-content: space-between; }
.member-identity { display: flex; align-items: center; gap: 12px; overflow-wrap: anywhere; }
.member-avatar { width: 34px; height: 34px; display: grid; place-items: center; flex: none; border-radius: 50%; background: #e9f1ec; color: #52806c; font-weight: 700; }
.rank-badge { display: grid; place-items: center; flex: none; width: 30px; height: 30px; background: #f0f3f1; color: #7f8c85; font-weight: 700; border-radius: 8px; }
.rank-badge.top1 { background: #fff0cc; color: #a5791d; }
.rank-badge.top2 { background: #e7edf3; color: #708299; }
.rank-badge.top3 { background: #f8e7db; color: #a97d5e; }
.rank-name { width: 110px; overflow-wrap: anywhere; flex-shrink: 0; }
.rank-bar, .stats-bar { height: 7px; border-radius: 8px; background: #eef3f0; overflow: hidden; flex: 1; }
.rank-bar-fill, .stats-bar-fill { height: 100%; border-radius: inherit; background: #63a28a; }
.rank-num, .stats-num { width: 45px; flex: none; text-align: right; color: #477b64; font-variant-numeric: tabular-nums; }
.stats-toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 14px; padding: 20px; margin-bottom: 14px; border-radius: 12px; background: #edf5ef; }
.stats-toolbar .meta { color: #648171; }
.stats-toolbar strong { font-size: 26px; color: #386b52; margin-left: 10px; }
.stats-row > span:first-child { width: 180px; flex-shrink: 0; overflow-wrap: anywhere; }
.ai-report { border: 1px solid var(--class-border); border-radius: 12px; background: #fff; padding: 24px; margin-top: 20px; line-height: 1.9; }
.ai-report :deep(h4) { color: #276650; }
.discussion-intro { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px; margin-bottom: 22px; }
.discussion-intro h2 { margin: 6px 0 0; font-size: 22px; letter-spacing: -.5px; color: #304b3e; }
.discussion-tools { display: flex; align-items: center; gap: 16px; }
.topic-count { color: #8b9991; font-size: 12px; }
.discussion-composer { background: #f2f7f3; }
.composer-heading { display: flex; justify-content: space-between; align-items: start; }
.composer-mark { color: #74a88c; font-size: 24px; }
.composer-fields { display: grid; gap: 12px; }
.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 16px; color: #87968b; font-size: 12px; }
.post-card { background: #fff; border: 1px solid var(--class-border); border-radius: 12px; padding: 24px; margin-bottom: 16px; }
.post-heading { display: flex; gap: 13px; align-items: center; }
.post-avatar, .comment-avatar { display: grid; place-items: center; flex: none; border-radius: 50%; background: #e9f2ec; color: #548267; font-weight: 700; }
.post-avatar { width: 40px; height: 40px; }
.post-card:nth-of-type(3n) .post-avatar { background: #f8efd9; color: #a2854e; }
.post-card:nth-of-type(3n+1) .post-avatar { background: #e7eff7; color: #5e7b9d; }
.post-title-wrap { display: flex; flex-direction: column; gap: 3px; flex: 1; min-width: 0; }
.post-title-wrap strong { font-size: 17px; color: #30453b; overflow-wrap: anywhere; }
.post-content { margin: 16px 0 20px 53px; line-height: 1.85; color: #627267; white-space: pre-wrap; overflow-wrap: anywhere; }
.comment-row { display: flex; align-items: flex-start; gap: 10px; margin: 8px 0 0 53px; }
.comment-avatar { width: 26px; height: 26px; font-size: 12px; background: #eff3f0; }
.comment { flex: 1; min-width: 0; padding: 8px 12px; border-radius: 8px; background: #f6f8f6; font-size: 13px; color: #718074; overflow-wrap: anywhere; white-space: pre-wrap; }
.comment-author { font-weight: 600; color: #446c53; }
.post-actions { display: flex; align-items: center; gap: 8px; margin: 18px 0 0 53px; padding-top: 16px; border-top: 1px solid #edf1ee; }
.post-actions .el-input { min-width: 0; }
.join-box { max-width: 620px; border: 1px solid var(--class-border); border-radius: 14px; padding: 24px; background: #fff; margin-top: 24px; }
.join-heading { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.join-icon { display: grid; place-items: center; width: 44px; height: 44px; flex: none; border-radius: 12px; background: #f8efdb; color: #a98840; font-size: 26px; }
.join-heading h3 { margin: 0; font-size: 17px; }
.join-heading p { margin: 4px 0 0; color: #89978e; font-size: 12px; }
.join-actions { display: flex; gap: 12px; align-items: center; }
.course-empty-card, .empty-state, .text-tertiary { border: 1px dashed #d7e1da; border-radius: 12px; padding: 40px 24px; background: #fafcf9; color: #8c9a8f; text-align: center; }
.course-empty-card { display: flex; gap: 18px; align-items: center; text-align: left; }
.course-empty-card p { margin: 5px 0 0; font-size: 13px; }
.course-empty-icon { font-size: 32px; color: #9eb3a2; }
.course-empty-card .el-button { margin-left: auto; flex-shrink: 0; }
.question-picker { max-height: 60vh; overflow-y: auto; padding: 0 8px; }
.picker-title { position: sticky; top: 0; z-index: 1; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; padding: 12px; background: #f0f6f2; color: #466954; border-radius: 8px; margin-bottom: 12px; }
.picker-title span { font-size: 12px; }
.question-option { display: flex !important; width: 100%; height: auto !important; align-items: flex-start !important; margin: 0 !important; padding: 16px 8px; border-bottom: 1px solid #e7ede8; }
.question-option :deep(.el-checkbox__input) { margin-top: 5px; flex: none; }
.question-option :deep(.el-checkbox__label) { display: block; min-width: 0; white-space: normal; line-height: 1.7; padding-left: 12px; overflow-wrap: anywhere; }
.question-detail strong { display: block; color: #344c3e; font-size: 14px; }
.question-options { color: #7a897e; margin: 8px 0; font-size: 13px; }
.question-answer { display: inline-block; border-radius: 5px; background: #edf6ef; padding: 3px 8px; color: #428054; font-size: 12px; }
.question-empty { padding: 24px; color: #8b997f; text-align: center; }
@media(max-width: 700px) {
  .cr-header { align-items: flex-start; }
  .page-title { font-size: 24px; }
  .header-caption { font-size: 12px; }
  .cr-detail-head { padding: 20px 18px 0; }
  .class-summary { gap: 18px; }
  .class-summary b { font-size: 20px; }
  .cr :deep(.el-tabs__item) { padding: 0 14px; }
  .inline-form, .post-card, .list-item, .task-card { padding: 18px; }
  .course-card { padding-left: 72px; }
  .course-card::before { left: 18px; }
  .course-link-panel .panel-intro, .member-form .panel-intro { flex-basis: 100%; }
  .course-link-panel .el-select, .member-form .el-input { flex: 1; min-width: 120px; width: auto !important; }
  .post-content, .comment-row, .post-actions { margin-left: 0; }
  .post-actions { flex-wrap: wrap; }
  .post-actions .el-input { flex-basis: 100% !important; }
  .stats-row > span:first-child { width: 100px; }
  .rank-name { width: 70px; }
  .member-row, .rank-row, .stats-row { gap: 10px; padding: 14px 10px; }
  .course-empty-card { flex-wrap: wrap; }
}
@media(prefers-reduced-motion: reduce) { .cr-card { transition: none; } }

.class-summary span:nth-child(1) b { color: #527ec5; }
.class-summary span:nth-child(2) b { color: #c08c43; }
.class-summary span:nth-child(3) b { color: #9780b9; }
.course-link-panel { background: #eff5fe; border-color: #dae6f6; }
.member-form { background: #edf6f3; border-color: #dcece5; }
.announcement-card { background: #fffefa; }
.class-monogram { background: #eaf1fd; color: #527ac0; }
.class-monogram:nth-child(1) { box-shadow: none; }
.task-card .list-item-head strong { color: #8f704a; }
.discussion-intro .section-kicker { color: #977bb2; }
.discussion-composer { background: #f8f5fc; border-color: #e8e0f1; }
.composer-mark { color: #b59ace; }
.post-card:nth-of-type(3n) .post-avatar { background: #fff0d8; color: #b38b49; }
.post-card:nth-of-type(3n+1) .post-avatar { background: #edf0fc; color: #7c82bb; }
.post-card:nth-of-type(3n+2) .post-avatar { background: #e7f4ef; color: #669d8b; }
.stats-toolbar { background: #edf3fc; }
.stats-toolbar strong { color: #587fb7; }
.rank-bar-fill { background: #e0b566; }
.stats-bar-fill { background: #80a4db; }
</style>
