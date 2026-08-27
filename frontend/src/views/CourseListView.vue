<template>
  <div class="course-list">
    <header class="page-header">
      <div class="page-header-left">
        <h1 class="page-title">课程列表</h1>
        <p class="page-desc" v-if="auth.isStudent">浏览课程，开始你的知识探索之旅</p>
        <p class="page-desc" v-else>管理你的课程内容与知识图谱</p>
      </div>
      <div class="page-header-right" v-if="auth.isTeacher">
        <el-button type="primary" @click="showCreateDialog = true" class="create-btn">
          <el-icon :size="16"><Plus /></el-icon>
          创建课程
        </el-button>
      </div>
    </header>

    <div class="course-grid" v-loading="loading">
      <template v-if="courses.length">
        <article
          v-for="(course, idx) in courses"
          :key="course.id"
          class="course-card"
          :style="{ '--card-accent': cardAccent(idx) }"
          @click="goDetail(course.id)"
        >
          <div class="course-card-body">
            <div class="course-card-top">
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
            <el-button text size="small" @click="goDetail(course.id)">查看详情</el-button>
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
        <el-button v-if="auth.isTeacher" type="primary" @click="showCreateDialog = true" style="margin-top: var(--space-4)">
          创建课程
        </el-button>
      </div>
    </div>

    <!-- 创建 / 编辑对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingCourse ? '编辑课程' : '创建课程'"
      width="480px"
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Collection, Document, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { coursesAPI, type CourseItem } from '@/api/courses'

const router = useRouter()
const auth = useAuthStore()

const ACCENTS = ['#1e40af','#4c1d95','#9d174d','#9a3412','#164e63','#166534','#701a75','#854d0e']

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
.course-list { max-width: 1100px; margin: 0 auto; }

.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: var(--space-8); }
.page-title { font-size: var(--font-size-3xl); font-weight: 700; margin: 0; color: var(--color-text-primary); }
.page-desc { margin: var(--space-2) 0 0; color: var(--color-text-secondary); font-size: var(--font-size-sm); }

.create-btn { padding: 10px 20px; font-weight: 600; }

.course-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: var(--space-5); min-height: 200px; }

.course-card {
  display: flex; flex-direction: column; border-radius: var(--radius-lg);
  border: 2px solid; cursor: pointer; background: #fff;
  transition: all var(--duration-normal) var(--ease-out);
  overflow: hidden;
}
.course-card:hover { box-shadow: var(--shadow-lg); transform: translateY(-2px); }

.course-card-body { flex: 1; padding: var(--space-5); display: flex; flex-direction: column; background: #fff; }

.course-card-top { flex: 1; margin-bottom: var(--space-4); }
.course-card-title { font-size: var(--font-size-lg); font-weight: 700; color: var(--color-text-primary); margin: 0 0 var(--space-2); line-height: var(--line-height-tight); }
.course-card-desc {
  font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin: 0;
  line-height: var(--line-height-base); display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}

.course-card-meta { display: flex; flex-wrap: wrap; gap: var(--space-4); padding-top: var(--space-4); border-top: 1px solid #f1f5f9; }
.meta-item { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--color-text-tertiary); }

.course-card-actions { display: flex; gap: var(--space-1); padding: var(--space-3) var(--space-5); border-top: 1px solid #f1f5f9; background: #fff; }

.empty-state { grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 320px; }
.empty-icon { font-size: 56px; margin-bottom: var(--space-4); opacity: 0.6; }
.empty-title { font-size: var(--font-size-md); font-weight: 600; color: var(--color-text-secondary); margin: 0 0 var(--space-2); }
.empty-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin: 0; }
.course-list { max-width:1180px; }
.page-header { margin-bottom:28px; padding:4px 2px; }
.page-title { letter-spacing:-.03em; }
.page-desc { color:#64748b; }
.create-btn { box-shadow:0 5px 14px rgba(34,197,94,.18); }
.course-grid { grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; }
.course-card { border:1px solid #cbd5e1 !important; border-top:5px solid var(--card-accent, #1e40af) !important; border-radius:16px; background:#fff !important; box-shadow:0 3px 12px rgba(15,23,42,.08); }
.course-card:hover { border-color:#94a3b8 !important; border-top-color:var(--card-accent) !important; box-shadow:0 14px 30px rgba(15,23,42,.18); transform:translateY(-3px); }
.course-card-body { padding:22px; background:#fff; }
.course-card-title { font-size:18px; letter-spacing:-.02em; }
.course-card-desc { color:#64748b; }
.course-card-meta { gap:12px; }
.course-card-actions { background:#fbfcfa; padding:10px 16px; }
.empty-state { min-height:360px; border:1px dashed #cbd5e1; border-radius:16px; background:#fbfcfa; }
</style>
