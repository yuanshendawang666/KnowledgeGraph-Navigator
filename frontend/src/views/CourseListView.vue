<template>
  <div class="course-list">
    <header class="page-header">
      <div class="page-header-left">
        <span class="section-kicker">课程学习空间</span><h1 class="page-title">课程列表</h1>
        <p class="page-desc" v-if="auth.isStudent">浏览课程，开始你的知识探索之旅</p>
        <p class="page-desc" v-else>管理你的课程内容与知识图谱</p>
      </div>
      <div class="page-header-right" v-if="auth.isTeacher">
        <el-button type="primary" @click="openCreate" class="create-btn">
          <el-icon :size="16"><Plus /></el-icon>
          创建课程
        </el-button>
      </div>
    </header>

    <div class="course-filter"><div><strong>全部课程</strong><span>{{ courses.length }} 门课程 · 持续探索，逐步积累</span></div><el-input v-model="searchText" clearable placeholder="搜索课程名称或简介" aria-label="搜索课程" /></div>
    <div class="course-grid" v-loading="loading">
      <template v-if="filteredCourses.length">
        <article
          v-for="(course, idx) in filteredCourses"
          :key="course.id"
          class="course-card"
          :style="{ '--card-accent': cardAccent(idx) }"
          tabindex="0" @keydown.enter.self="goDetail(course.id)"
          @click="goDetail(course.id)"
        >
          <div class="course-card-body">
            <div class="course-cover"><el-icon :size="32"><Collection /></el-icon><span>课程知识库</span><span class="cover-number">{{ String(idx + 1).padStart(2, '0') }}</span></div><div class="course-card-top">
              <h3 class="course-card-title">{{ course.title }}</h3>
              <p class="course-card-desc">{{ course.description || '暂无简介' }}</p>
            </div>
            <div class="course-card-meta">
              <span class="meta-item" :style="{ color: cardAccent(idx) }">
                <el-icon :size="14"><Collection /></el-icon>
                {{ course.knowledge_point_count }} 知识点
              </span>
              <span class="meta-item">
                <el-icon :size="14"><Document /></el-icon>
                {{ course.document_count }} 文档
              </span>
              <span class="meta-item" v-if="course.teacher_name">
                <el-icon :size="14"><User /></el-icon>
                {{ course.teacher_name }}
              </span>
            </div>
          </div>
          <div class="course-card-actions" @click.stop>
            <el-button text size="small" @click="goDetail(course.id)">进入课程 →</el-button>
            <template v-if="auth.isTeacher && auth.user?.id === course.teacher_id">
              <el-button text size="small" type="warning" @click="editCourse(course)">编辑</el-button>
              <el-button text size="small" type="danger" @click="confirmDelete(course)">删除</el-button>
            </template>
          </div>
        </article>
      </template>

      <div v-if="!loading && courses.length === 0" class="empty-state">
        <span class="empty-icon">📚</span>
        <p class="empty-title">还没有课程</p>
        <p class="empty-desc" v-if="auth.isTeacher">创建你的第一门课程，开始构建知识图谱</p>
        <p class="empty-desc" v-else>暂时没有可用的课程，请联系教师创建</p>
        <el-button v-if="auth.isTeacher" type="primary" @click="openCreate" style="margin-top: var(--space-4)">
          创建课程
        </el-button>
      </div>
    </div>

    <div v-if="!loading && courses.length && !filteredCourses.length" class="empty-state"><p class="empty-title">没有找到相关课程</p><p class="empty-desc">试试其他关键词，或清空搜索查看全部课程。</p><el-button text @click="searchText = ''">清空搜索</el-button></div>
    <!-- 创建 / 编辑对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingCourse ? '编辑课程' : '创建课程'"
      width="min(520px, 94vw)"
      destroy-on-close
    >
      <el-form :model="courseForm" :rules="courseRules" label-position="top">
        <el-form-item label="课程名称" prop="title">
          <el-input v-model="courseForm.title" placeholder="例如：Python 程序设计" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="课程简介" prop="description">
          <el-input v-model="courseForm.description" type="textarea" :rows="3" placeholder="简要描述课程内容与目标…" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSaveCourse">
          {{ editingCourse ? '保存修改' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Collection, Document, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { coursesAPI, type CourseItem } from '@/api/courses'

const router = useRouter()
const auth = useAuthStore()

const searchText = ref('')
const filteredCourses = computed(() => { const keyword = searchText.value.trim().toLowerCase(); return courses.value.filter(c => `${c.title} ${c.description || ''}`.toLowerCase().includes(keyword)) })

const ACCENTS = ['#477d70', '#547aa5', '#a18045', '#826c90']

function cardAccent(idx: number) { return ACCENTS[idx % ACCENTS.length] }

const courses = ref<CourseItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showCreateDialog = ref(false)
const editingCourse = ref<CourseItem | null>(null)
const courseForm = reactive({ title: '', description: '' })

const courseRules: FormRules = {
  title: [
    { required: true, message: '请输入课程名称', trigger: 'blur' },
    { min: 2, max: 100, message: '课程名称在 2 到 100 个字符', trigger: 'blur' },
  ],
}

async function fetchCourses() {
  loading.value = true
  try { courses.value = await coursesAPI.getList() } catch {} finally { loading.value = false }
}

function goDetail(id: number) { router.push(`/course/${id}`) }

function openCreate() {
  editingCourse.value = null
  courseForm.title = ''
  courseForm.description = ''
  showCreateDialog.value = true
}

function editCourse(course: CourseItem) {
  editingCourse.value = course
  courseForm.title = course.title
  courseForm.description = course.description
  showCreateDialog.value = true
}

async function handleSaveCourse() {
  if (!courseForm.title.trim()) {
    ElMessage.warning('请输入课程名称')
    return
  }
  saving.value = true
  try {
    if (editingCourse.value) {
      await coursesAPI.update(editingCourse.value.id, { title: courseForm.title, description: courseForm.description })
    } else {
      const res = await coursesAPI.create({ title: courseForm.title.trim(), description: courseForm.description.trim() })
      ElMessage.success('课程创建成功: ' + res.title)
    }
    showCreateDialog.value = false; editingCourse.value = null
    courseForm.title = ''; courseForm.description = ''
    await fetchCourses()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e?.response?.data?.detail || e?.message || '未知'))
  } finally { saving.value = false }
}

async function confirmDelete(course: CourseItem) {
  try {
    await ElMessageBox.confirm(`确定删除"${course.title}"？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await coursesAPI.delete(course.id)
    ElMessage.success('已删除')
    await fetchCourses()
  } catch {}
}

onMounted(fetchCourses)
</script>

<style scoped>
.course-list { max-width: 1160px; margin: 0 auto; padding: 12px 0 40px; color: #34445d; --el-color-primary: #356bc4; --el-color-primary-light-9: #edf3fc; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 20px; margin-bottom: 30px; }
.section-kicker { color: #356bc4; font-size: 12px; font-weight: 700; letter-spacing: 2px; }
.page-title { font-size: 30px; margin: 6px 0; letter-spacing: -.7px; color: #243856; }
.page-desc { font-size: 14px; margin: 8px 0 0; color: #8490a3; }
.course-list :deep(.el-button) { border-radius: 8px; box-shadow: none; font-weight: 600; }
.course-list :deep(.el-button--primary:not(.is-text)) { background: #356bc4; border-color: #356bc4; }
.create-btn { height: 40px; padding: 10px 18px; gap: 6px; }
.course-filter { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; margin-bottom: 22px; padding-bottom: 20px; border-bottom: 1px solid #dfe8e1; }
.course-filter strong { font-size: 16px; margin-right: 16px; }
.course-filter span { font-size: 12px; color: #8a978e; }
.course-filter .el-input { width: 280px; max-width: 100%; }
.course-list :deep(.el-input__wrapper), .course-list :deep(.el-textarea__inner) { border-radius: 8px; min-height: 40px; box-shadow: 0 0 0 1px #dce6df inset; }
.course-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(290px, 100%), 1fr)); gap: 22px; }
.course-card { display: flex; flex-direction: column; border: 1px solid #e0e8e2; background: #fff; border-radius: 14px; overflow: hidden; cursor: pointer; transition: transform .18s, box-shadow .18s; min-width: 0; }
.course-card:hover { transform: translateY(-4px); box-shadow: 0 12px 26px #1c413511; }
.course-card:focus-visible { outline: 2px solid #356bc4; outline-offset: 3px; }
.course-card-body { flex: 1; padding: 18px; display: flex; flex-direction: column; }
.course-cover { position: relative; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; gap: 10px; height: 112px; padding: 20px; border-radius: 9px; margin-bottom: 20px; background: color-mix(in srgb, var(--card-accent) 10%, white); color: var(--card-accent); overflow: hidden; }
.course-cover > span:not(.cover-number) { font-size: 11px; letter-spacing: 2px; }
.cover-number { position: absolute; right: 10px; bottom: -24px; font-size: 110px; line-height: 1.2; font-family: Georgia, serif; opacity: .12; pointer-events: none; }
.course-card-top { flex: 1; margin-bottom: 22px; }
.course-card-title { font-size: 19px; margin: 0 0 10px; color: #304564; overflow-wrap: anywhere; }
.course-card-desc { font-size: 13px; margin: 0; line-height: 1.75; color: #829086; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; min-height: 45px; }
.course-card-meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: #819086; }
.meta-item { display: inline-flex; align-items: center; gap: 5px; }
.course-card-actions { display: flex; align-items: center; gap: 2px; border-top: 1px solid #eff2ef; padding: 10px 16px; }
.course-card-actions .el-button:first-child { margin-right: auto; color: var(--card-accent); font-weight: 700; }
.empty-state { grid-column: 1/-1; display: flex; align-items: center; justify-content: center; flex-direction: column; min-height: 290px; padding: 30px; border: 1px dashed #d3dfd6; border-radius: 14px; text-align: center; background: #fafcf9; }
.empty-icon { font-size: 42px; opacity: .65; }
.empty-title { font-size: 18px; margin: 15px 0 8px; color: #59725f; }
.empty-desc { font-size: 13px; color: #8b9b8e; }
@media(max-width: 700px) { .page-header { align-items: flex-start; } .page-title { font-size: 25px; } .course-filter .el-input { width: 100%; } .course-filter span { display: block; margin-top: 6px; } }
@media(prefers-reduced-motion: reduce) { .course-card { transition: none; } }

.course-filter strong { color: #365c91; }
.course-cover { height: 126px; }
.course-card:nth-child(4n+1) { --card-accent: #3d78cc !important; }
.course-card:nth-child(4n+2) { --card-accent: #c18c38 !important; }
.course-card:nth-child(4n+3) { --card-accent: #5b9c90 !important; }
.course-card:nth-child(4n) { --card-accent: #9b7cc0 !important; }
</style>
