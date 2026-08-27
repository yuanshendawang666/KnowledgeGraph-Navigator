<template>
  <div class="course-detail">
    <!-- 返回 -->
    <button class="back-link" @click="$router.push('/')">
      <el-icon :size="16"><ArrowLeft /></el-icon>
      返回课程列表
    </button>

    <!-- 课程信息头部 -->
    <header class="detail-header" v-loading="loading">
      <div class="header-main">
        <h1 class="detail-title">{{ course?.title }}</h1>
        <p class="detail-desc">{{ course?.description || '暂无简介' }}</p>
        <div class="detail-meta">
          <el-tag type="info" size="small" round>知识点 {{ course?.knowledge_point_count || 0 }}</el-tag>
          <el-tag type="info" size="small" round>文档 {{ course?.document_count || 0 }}</el-tag>
          <el-tag v-if="course?.teacher_name" size="small" round>{{ course.teacher_name }}</el-tag>
        </div>
      </div>
      <div class="header-actions" v-if="auth.isTeacher && course?.teacher_id === auth.user?.id">
        <!-- 上传文档 — 琥珀色包裹，整行可点击 -->
        <el-upload
          :action="`/api/courses/${courseId}/upload`"
          :headers="uploadHeaders"
          :before-upload="beforeUpload"
          :on-success="onUploadSuccess"
          :on-error="onUploadError"
          :show-file-list="false"
          accept=".pdf,.docx,.doc,.md,.txt,.png,.jpg,.jpeg,.tiff,.bmp"
          class="upload-full-wrap"
        >
          <div class="action-wrap action-upload">
            <el-icon :size="18" class="action-wrap-icon"><Upload /></el-icon>
            <span class="action-wrap-label">上传课件文档</span>
            <el-icon :size="14" class="action-wrap-arrow"><Plus /></el-icon>
          </div>
        </el-upload>
        <!-- 知识提取 — 蓝色包裹，整行可点击 -->
        <div
          class="action-wrap action-extract"
          :class="{ disabled: !hasDocuments }"
          @click="extractKnowledge"
        >
          <el-icon :size="18" class="action-wrap-icon"><MagicStick /></el-icon>
          <span class="action-wrap-label">AI 知识提取</span>
          <el-icon v-if="!extracting" :size="14" class="action-wrap-arrow"><ArrowRight /></el-icon>
          <el-icon v-else class="is-loading" :size="14"><Loading /></el-icon>
        </div>
      </div>
    </header>

    <!-- 内容区 -->
    <div class="detail-content">
      <!-- 知识图谱 -->
      <section class="content-section graph-section">
        <div class="section-header">
          <h2 class="section-title">知识图谱</h2>
          <div style="display:flex;gap:4px;align-items:center">
            <el-button-group size="small" v-if="hasGraph">
              <el-button :type="graphDepth===0?'primary':''" @click="setDepth(0)">仅模块</el-button>
              <el-button :type="graphDepth===1?'primary':''" @click="setDepth(1)">+子模块</el-button>
              <el-button :type="graphDepth===2?'primary':''" @click="setDepth(2)">全部</el-button>
            </el-button-group>
            <el-button v-if="hasGraph" text size="small" type="danger" @click="clearGraph" style="margin-left:8px">清除图谱</el-button>
          </div>
        </div>
        <KnowledgeGraph :data="graphData" :loading="graphLoading" @node-click="onNodeClick" @node-contextmenu="onNodeContextMenu" />
      </section>

      <!-- 知识点列表 + 操作入口 -->
      <div class="content-side">
        <!-- 已上传文档 -->
        <section class="content-section" v-if="auth.isTeacher && course?.teacher_id === auth.user?.id">
          <div class="section-header">
            <h2 class="section-title">已上传文档</h2>
            <span class="section-count">{{ documents.length }} 个</span>
          </div>
          <div v-if="documents.length" class="doc-list">
            <div v-for="doc in documents" :key="doc.id" class="doc-item">
              <el-icon :size="14" class="doc-icon"><Document /></el-icon>
              <span class="doc-name" @click="viewDocument(doc)">{{ doc.filename }}</span>
              <span class="doc-status" :class="doc.status">{{ statusLabel(doc.status) }}</span>
              <button class="doc-delete" @click.stop="deleteDocument(doc)" title="删除文档">
                <el-icon :size="12"><Close /></el-icon>
              </button>
            </div>
          </div>
          <div v-else class="inline-empty">
            <span class="text-tertiary" style="font-size: var(--font-size-xs)">暂无文档</span>
          </div>
        </section>

        <!-- 知识点树 -->
        <section class="content-section">
          <div class="section-header" style="flex-wrap:wrap">
            <h2 class="section-title">知识点结构</h2>
            <span class="section-badge" v-if="knowledgePoints.length">{{ knowledgePoints.length }} 个</span>
            <div style="display:flex;gap:8px;width:100%;margin-top:4px">
              <el-button text size="small" type="primary" @click="goAllKnowledgePoints">
                <el-icon :size="14"><View /></el-icon> 查看全部
              </el-button>
              <el-button v-if="auth.isTeacher" text size="small" type="primary" @click="showAddKpDialog(rootNodeId)">
                <el-icon :size="14"><Plus /></el-icon> 添加
              </el-button>
            </div>
          </div>
          <div v-if="knowledgeTree.length" class="kp-tree">
            <div v-for="mod in knowledgeTree" :key="mod.id" class="tree-module">
              <div class="tree-node mod">
                <span style="flex:1;display:flex;align-items:center;gap:8px">
                  <el-icon :size="14" class="tree-arrow" :class="{open: expandedModules.has(mod.id)}" @click="toggleModule(mod.id)"><ArrowDown /></el-icon>
                  <span class="tree-name" @click="showNodeDetail(mod)">{{ mod.label }}</span>
                  <span class="tree-count">{{ countLeaves(mod) }}个</span>
                </span>
                <span v-if="auth.isTeacher" class="kp-actions">
                  <button class="kp-btn" @click.stop="editKp(mod)" title="编辑"><el-icon :size="12"><Edit /></el-icon></button>
                  <button class="kp-btn" @click.stop="enhanceDesc(mod)" title="AI优化简介"><el-icon :size="12"><MagicStick /></el-icon></button>
                  <button class="kp-btn danger" @click.stop="deleteKp(mod)" title="删除"><el-icon :size="12"><Delete /></el-icon></button>
                </span>
              </div>
              <div v-show="expandedModules.has(mod.id)" class="tree-children">
                <div v-for="sub in mod.children" :key="sub.id" class="tree-submodule">
                  <div class="tree-node sub" @click="showNodeDetail(sub)">
                    <span class="tree-dot"></span>
                    <span class="tree-name">{{ sub.label }}</span>
                    <span v-if="auth.isTeacher" class="kp-actions">
                      <button class="kp-btn" @click.stop="editKp(sub)" title="编辑"><el-icon :size="11"><Edit /></el-icon></button>
                      <button class="kp-btn danger" @click.stop="deleteKp(sub)" title="删除"><el-icon :size="11"><Delete /></el-icon></button>
                    </span>
                  </div>
                  <div class="tree-leaves">
                    <div v-for="kp in sub.children" :key="kp.id" class="tree-node kp" @click="showNodeDetail(kp)">
                      <span class="tree-name">{{ kp.label }}</span>
                      <span v-if="auth.isTeacher" class="kp-actions">
                        <button class="kp-btn" @click.stop="editKp(kp)" title="编辑"><el-icon :size="10"><Edit /></el-icon></button>
                        <button class="kp-btn danger" @click.stop="deleteKp(kp)" title="删除"><el-icon :size="10"><Delete /></el-icon></button>
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="inline-empty">
            <span>暂无知识点，上传文档后进行知识提取</span>
          </div>

          <!-- 编辑知识点对话框 -->
          <el-dialog v-model="editDialogVisible" :title="editMode==='add'?'添加知识点':'编辑知识点'" width="480px">
            <el-form label-position="top">
              <el-form-item label="名称">
                <el-input v-model="editForm.name" placeholder="知识点名称" />
              </el-form-item>
              <el-form-item label="简介">
                <el-input v-model="editForm.description" type="textarea" :rows="4" placeholder="知识点简介" />
              </el-form-item>
              <el-form-item label="类型">
                <el-select v-model="editForm.level" style="width:100%">
                  <el-option :value="0" label="根模块" />
                  <el-option :value="1" label="子模块" />
                  <el-option :value="2" label="叶子知识点" />
                </el-select>
              </el-form-item>
              <el-form-item label="父节点ID（可选）">
                <el-input v-model="editForm.parent_id" placeholder="留空为根模块" />
              </el-form-item>
            </el-form>
            <template #footer>
              <el-button @click="editDialogVisible=false">取消</el-button>
              <el-button type="primary" @click="saveKp">保存</el-button>
            </template>
          </el-dialog>

          <!-- 知识点简介弹窗 -->
          <el-dialog v-model="nodeDetailVisible" :title="nodeDetail?.label" width="460px">
            <div class="kp-detail-tag">
              <el-tag v-if="nodeDetail?.level === 0" type="primary" size="small">模块</el-tag>
              <el-tag v-else-if="nodeDetail?.level === 1" size="small" style="background:#eef2ff;color:#4f46e5;border-color:#c7d2fe">子模块</el-tag>
              <el-tag v-else size="small" type="info">知识点</el-tag>
            </div>
            <p class="kp-detail-desc">{{ nodeDetail?.description || '暂无简介' }}</p>
            <template #footer>
              <el-button @click="nodeDetailVisible=false">关闭</el-button>
              <el-button v-if="nodeDetail?.sqlite_id && !nodeDetail?.is_module" type="primary" @click="goNodeDetail">查看完整详情</el-button>
            </template>
          </el-dialog>
        </section>

        <!-- 快捷操作 — 彩色包裹 -->
        <section class="content-section">
          <div class="section-header">
            <h2 class="section-title">学习操作</h2>
          </div>
          <div class="action-buttons">
            <!-- 查看进度 — 蓝色背景 -->
            <div class="action-card action-progress" @click="goProgress">
              <span class="action-card-icon">
                <el-icon :size="22"><TrendCharts /></el-icon>
              </span>
              <div class="action-card-body">
                <span class="action-card-title">查看学习进度</span>
                <span class="action-card-desc">追踪每个知识点的掌握状态</span>
              </div>
              <el-icon :size="16" class="action-card-arrow"><ArrowRight /></el-icon>
            </div>

            <!-- 获取推荐 — 绿色背景 -->
            <div class="action-card action-recommend" @click="goRecommend">
              <span class="action-card-icon">
                <el-icon :size="22"><Guide /></el-icon>
              </span>
              <div class="action-card-body">
                <span class="action-card-title">获取学习推荐</span>
                <span class="action-card-desc">AI 分析最佳学习路径</span>
              </div>
              <el-icon :size="16" class="action-card-arrow"><ArrowRight /></el-icon>
            </div>

          </div>
        </section>
      </div>
    </div>

    <!-- 文档内容弹窗 -->
    <el-dialog v-model="docDialogVisible" :title="docDetail?.filename" width="700px" destroy-on-close>
      <div class="doc-detail-content" v-if="docDetail">
        <div class="doc-detail-meta">
          <el-tag :type="docDetail.status === 'extracted' ? 'success' : 'info'" size="small">
            {{ statusLabel(docDetail.status) }}
          </el-tag>
          <span class="text-tertiary" style="font-size:var(--font-size-xs)">
            {{ docDetail.parsed_length }} 字符 &middot; {{ docDetail.created_at }}
          </span>
        </div>
        <pre class="doc-detail-text">{{ docDetail.parsed_content || '暂无解析内容' }}</pre>
      </div>
    </el-dialog>

    <!-- AI 问答浮动面板 -->
    <ChatPanel :course-id="courseId" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Upload, TrendCharts, Guide, MagicStick, ArrowRight, Plus, Loading, Document, Close, ArrowDown, Edit, Delete, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { coursesAPI, type CourseDetail, type GraphData, type KnowledgePointItem, type DocumentItem, type TreeNode } from '@/api/courses'
import type { UploadProps } from 'element-plus'
import KnowledgeGraph from '@/components/KnowledgeGraph.vue'
import ChatPanel from '@/components/ChatPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const courseId = computed(() => Number(route.params.id))

const course = ref<CourseDetail | null>(null)
const graphData = ref<GraphData | null>(null)
const knowledgePoints = ref<KnowledgePointItem[]>([])
const documents = ref<DocumentItem[]>([])
const docDetail = ref<any>(null)
const docDialogVisible = ref(false)
const loading = ref(false)
const graphLoading = ref(false)
const extracting = ref(false)
const graphDepth = ref(2)  // 图谱深度: 0=仅模块, 1=模块+子模块, 2=全部
const expandedModules = ref<Set<string>>(new Set())  // 展开的模块ID
const showAllKps = ref(false)  // 是否展开全部知识点

const hasDocuments = computed(() => (course.value?.document_count || 0) > 0)
const hasGraph = computed(() => (graphData.value?.nodes?.length || 0) > 0)
const knowledgeTree = computed(() => graphData.value?.tree || [])

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${auth.token}`,
}))

async function fetchCourse() {
  loading.value = true
  try {
    course.value = await coursesAPI.getDetail(courseId.value)
    knowledgePoints.value = course.value.knowledge_points || []
    await Promise.all([fetchGraph(), fetchDocuments()])
  } catch {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

async function fetchDocuments() {
  try {
    documents.value = await coursesAPI.getDocuments(courseId.value)
  } catch {
    documents.value = []
  }
}

async function deleteDocument(doc: DocumentItem) {
  try {
    await coursesAPI.deleteDocument(courseId.value, doc.id)
    ElMessage.success(`已删除 ${doc.filename}`)
    await fetchDocuments()
    await fetchCourse()
  } catch {
    // 错误已处理
  }
}

async function viewDocument(doc: DocumentItem) {
  try {
    const detail = await coursesAPI.getDocument(courseId.value, doc.id)
    docDetail.value = detail
    docDialogVisible.value = true
  } catch {
    ElMessage.error('获取文档详情失败')
  }
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    uploaded: '已上传',
    parsed: '已解析',
    extracted: '已提取',
    failed: '失败',
  }
  return map[status] || status
}

async function fetchGraph() {
  graphLoading.value = true
  try {
    graphData.value = await coursesAPI.getGraph(courseId.value, graphDepth.value)
  } catch {
    graphData.value = null
  } finally {
    graphLoading.value = false
  }
}

function setDepth(d: number) {
  graphDepth.value = d
  fetchGraph()
}

function toggleModule(id: string) {
  if (expandedModules.value.has(id)) {
    expandedModules.value.delete(id)
  } else {
    expandedModules.value.add(id)
  }
  // 触发响应式更新
  expandedModules.value = new Set(expandedModules.value)
}

function countLeaves(node: TreeNode): number {
  if (!node.children || !node.children.length) return 0
  let count = 0
  for (const child of node.children) {
    if (child.children && child.children.length) {
      count += child.children.length
    }
  }
  return count
}

// ── 知识点增删改 ──
const editDialogVisible = ref(false)
const editMode = ref<'add'|'edit'>('edit')
const editingKpId = ref<number>(0)
const rootNodeId = ref<number>(0)
const editForm = ref({ name: '', description: '', level: 2, parent_id: '' })

function showAddKpDialog(parentId: number) {
  editMode.value = 'add'
  editingKpId.value = 0
  editForm.value = { name: '', description: '', level: 2, parent_id: String(parentId || '') }
  editDialogVisible.value = true
}

function editKp(node: TreeNode) {
  editMode.value = 'edit'
  editingKpId.value = node.sqlite_id ?? 0
  editForm.value = {
    name: node.label,
    description: node.description || '',
    level: node.level,
    parent_id: '',
  }
  editDialogVisible.value = true
}

async function saveKp() {
  const payload = {
    name: editForm.value.name,
    description: editForm.value.description,
    level: editForm.value.level,
    is_module: editForm.value.level < 2,
    parent_id: editForm.value.parent_id ? Number(editForm.value.parent_id) : null,
  }
  try {
    if (editMode.value === 'add') {
      await http.post(`/courses/${courseId.value}/knowledge-points`, payload)
      ElMessage.success('知识点已添加')
    } else {
      await http.put(`/courses/${courseId.value}/knowledge-points/${editingKpId.value}`, payload)
      ElMessage.success('知识点已更新')
    }
    editDialogVisible.value = false
    await fetchGraph()
    await fetchCourse()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e?.response?.data?.detail || e?.message || ''))
  }
}

async function deleteKp(node: TreeNode) {
  try {
    await ElMessageBox.confirm(`确定删除「${node.label}」及其所有子节点吗？`, '确认删除', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await http.delete(`/courses/${courseId.value}/knowledge-points/${node.sqlite_id ?? 0}`)
    ElMessage.success(`已删除 ${node.label}`)
    await fetchGraph()
    await fetchCourse()
  } catch { /* cancelled */ }
}

async function enhanceDesc(node: TreeNode) {
  try {
    ElMessage.info('AI 正在优化简介...')
    const r: any = await http.post(`/courses/${courseId.value}/knowledge-points/${node.sqlite_id ?? 0}/enhance`)
    ElMessage.success(`简介已优化: ${r.enhanced_description.substring(0, 50)}...`)
    await fetchGraph()
    await fetchCourse()
  } catch (e: any) {
    ElMessage.error('AI优化失败: ' + (e?.response?.data?.detail || e?.message || ''))
  }
}

// 导入 http 用于手动调用
import http from '@/api/index'

const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const allowed = ['.pdf', '.docx', '.doc', '.md', '.txt', '.png', '.jpg', '.jpeg', '.tiff', '.bmp']
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!allowed.includes(ext)) {
    ElMessage.error(`不支持的文件格式：${ext}，支持 ${allowed.join(', ')}`)
    return false
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  return true
}

function onUploadSuccess() {
  ElMessage.success('文档上传成功')
  fetchCourse()
}

function onUploadError() {
  ElMessage.error('文档上传失败')
}

async function extractKnowledge() {
  extracting.value = true
  try {
    const res = await coursesAPI.extractKnowledge(courseId.value)
    ElMessage.success(`知识提取完成：${res.knowledge_points_count} 个知识点，${res.relations_count} 个关系`)
    await fetchCourse()
    await fetchGraph()
  } catch (e: any) {
    ElMessage.error('知识提取失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    extracting.value = false
  }
}

async function clearGraph() {
  try {
    await ElMessageBox.confirm('确定要清除该课程的知识图谱吗？', '确认', {
      confirmButtonText: '清除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await coursesAPI.deleteGraph(courseId.value)
    graphData.value = null
    knowledgePoints.value = []
    ElMessage.success('图谱已清除')
    await fetchCourse()
  } catch {
    // 取消或错误
  }
}

function goProgress() {
  router.push(`/progress/${courseId.value}`)
}

function goRecommend() {
  router.push(`/progress/${courseId.value}?tab=recommend`)
}

function onNodeClick(payload: { sqlite_id?: number; label: string; level?: number; is_module?: boolean; description?: string }) {
  // 左键点击图谱节点 → 弹窗查看节点详情
  showNodeDetail({
    id: '',
    label: payload.label,
    description: payload.description || '',
    order_index: 0,
    level: payload.level ?? 2,
    is_module: payload.is_module ?? false,
    sqlite_id: payload.sqlite_id,
    children: [],
  })
}

function onNodeContextMenu(payload: { sqlite_id?: number; label: string; level?: number; is_module?: boolean }) {
  // 右键节点 → 删除（仅课程创建者）
  if (!auth.isTeacher || course.value?.teacher_id !== auth.user?.id) {
    ElMessage.warning('仅课程创建者可删除知识点')
    return
  }
  if (!payload.sqlite_id) {
    ElMessage.warning('无法定位知识点')
    return
  }
  ElMessageBox.confirm(`确定删除「${payload.label}」及其所有子节点吗？`, '删除知识点', {
    confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
  }).then(async () => {
    try {
      await http.delete(`/courses/${courseId.value}/knowledge-points/${payload.sqlite_id}`)
      ElMessage.success(`已删除 ${payload.label}`)
      await fetchGraph()
      await fetchCourse()
    } catch (e: any) {
      ElMessage.error('删除失败: ' + (e?.response?.data?.detail || e?.message || ''))
    }
  }).catch(() => { /* 取消 */ })
}

function goAllKnowledgePoints() {
  router.push(`/course/${courseId.value}/knowledge`)
}

// ── 知识点简介弹窗 ──
const nodeDetailVisible = ref(false)
const nodeDetail = ref<TreeNode | null>(null)

function showNodeDetail(node: TreeNode) {
  nodeDetail.value = node
  nodeDetailVisible.value = true
}

function goNodeDetail() {
  if (nodeDetail.value?.sqlite_id) {
    nodeDetailVisible.value = false
    router.push(`/course/${courseId.value}/knowledge/${nodeDetail.value.sqlite_id}`)
  }
}

onMounted(fetchCourse)
</script>

<style scoped>
.course-detail {
  max-width: 1200px;
  margin: 0 auto;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  border: none;
  background: none;
  color: var(--color-text-tertiary);
  font-family: inherit;
  font-size: var(--font-size-sm);
  cursor: pointer;
  padding: 0;
  margin-bottom: var(--space-4);
  transition: color var(--duration-fast);
}
.back-link:hover { color: var(--color-text-primary); }

/* 课程头部 */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-6);
  margin-bottom: var(--space-8);
  padding: var(--space-8);
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 1.5px solid #93c5fd;
  border-radius: var(--radius-xl);
}

.header-main { flex: 1; min-width: 0; }
.detail-title {
  font-size: var(--font-size-3xl);
  font-weight: 700;
  margin: 0 0 var(--space-2);
  color: var(--color-text-primary);
}
.detail-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: 0 0 var(--space-4);
  line-height: var(--line-height-relaxed);
}
.detail-meta { display: flex; gap: var(--space-2); }

/* 操作按钮区 */
.header-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  flex-shrink: 0;
  width: 200px;
}

.upload-full-wrap {
  display: block;
  width: 100%;
}
.upload-full-wrap :deep(.el-upload) {
  display: block;
  width: 100%;
}

.action-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid transparent;
  cursor: pointer;
  width: 200px;
  box-sizing: border-box;
  transition: all var(--duration-normal) var(--ease-out);
  user-select: none;
}

.action-wrap:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.action-upload {
  background: linear-gradient(135deg, #fffbeb, #fef3c7);
  border-color: #fde68a;
}
.action-upload .action-wrap-icon { color: #d97706; }
.action-upload:hover { border-color: #fbbf24; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.15); }
.action-upload .action-wrap-label {
  flex: 1;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: #92400e;
}

.action-extract {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-color: #93c5fd;
}
.action-extract .action-wrap-icon { color: #2563eb; }
.action-extract:hover:not(.disabled) { border-color: #60a5fa; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15); }
.action-extract .action-wrap-label {
  flex: 1;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: #1e40af;
}

.action-extract.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.action-extract.disabled:hover {
  transform: none;
  box-shadow: none;
}

.action-wrap-arrow {
  color: currentColor;
  opacity: 0.5;
  flex-shrink: 0;
}

/* 内容区 */
.detail-content {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--space-6);
  align-items: start;
}
@media (max-width: 900px) { .detail-content { grid-template-columns: 1fr; } }

.content-section {
  background: var(--color-surface-default);
  border: 1.5px solid #93c5fd;
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  margin-bottom: var(--space-5);
}

.graph-section { padding: var(--space-5); }

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
  gap: var(--space-2);
}

.section-badge {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--color-brand-500);
  background: #eff6ff;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  margin-left: auto;
}

.kp-view-all {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: #f8fafc;
  color: var(--color-brand-500);
  text-decoration: none;
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: all var(--duration-fast);
}

.kp-view-all:hover {
  background: #eff6ff;
  color: #2563eb;
}
.section-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}

/* 知识点列表 */
.kp-list { display: flex; flex-direction: column; gap: var(--space-2); }
.kp-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  transition: background var(--duration-fast);
}
.kp-item:hover { background: var(--color-surface-overlay); }

.kp-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  background: #dbeafe;
  color: #2563eb;
  font-size: var(--font-size-xs);
  font-weight: 600;
  flex-shrink: 0;
}
.kp-info { flex: 1; min-width: 0; }
.kp-name { display: block; font-size: var(--font-size-sm); font-weight: 500; color: var(--color-text-primary); }
.kp-desc {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 彩色操作卡片 */
.action-buttons {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.action-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.action-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }

.action-progress {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border-color: #93c5fd;
}
.action-progress .action-card-icon { color: #2563eb; }
.action-progress:hover { border-color: #60a5fa; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15); }

.action-recommend {
  background: linear-gradient(135deg, #f0fdf4, #dcfce7);
  border-color: #86efac;
}
.action-recommend .action-card-icon { color: #16a34a; }
.action-recommend:hover { border-color: #4ade80; box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15); }

.action-quiz {
  background: linear-gradient(135deg, #f5f3ff, #ede9fe);
  border-color: #c4b5fd;
}
.action-quiz .action-card-icon { color: #7c3aed; }
.action-quiz:hover { border-color: #a78bfa; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.15); }

.action-card-body { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.action-card-title { font-size: var(--font-size-sm); font-weight: 600; color: var(--color-text-primary); }
.action-card-desc { font-size: var(--font-size-xs); color: var(--color-text-tertiary); }

.action-card-arrow { color: var(--color-text-placeholder); transition: transform var(--duration-fast); }
.action-card:hover .action-card-arrow { transform: translateX(3px); }

.inline-empty {
  padding: var(--space-4);
  text-align: center;
  border: 1px dashed #bfdbfe;
  border-radius: var(--radius-md);
}

/* 文档列表 */
.doc-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.doc-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: #f5f3ff;
  border: 1px solid #ddd6fe;
  transition: all var(--duration-fast);
}

.doc-item:hover { background: #ede9fe; border-color: #c4b5fd; }

.doc-icon { color: var(--color-text-tertiary); flex-shrink: 0; }

.doc-name {
  flex: 1;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-status {
  font-size: 10px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.doc-status.uploaded { background: #eff6ff; color: #2563eb; }
.doc-status.parsed { background: #f0fdf4; color: #16a34a; }
.doc-status.extracted { background: #dcfce7; color: #15803d; }
.doc-status.failed { background: #fef2f2; color: #dc2626; }

.doc-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 1.5px solid #a78bfa;
  border-radius: var(--radius-full);
  background: transparent;
  color: #7c3aed;
  cursor: pointer;
  transition: all var(--duration-fast);
  flex-shrink: 0;
}

.doc-delete:hover { background: #7c3aed; color: #fff; border-color: #7c3aed; }

.section-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

/* ── 知识树 ── */
.kp-tree { display: flex; flex-direction: column; gap: var(--space-2); }
.tree-module { border: 1px solid #e2e8f0; border-radius: var(--radius-md); overflow: hidden; }
.tree-node { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); cursor: pointer; transition: background .15s; }
.tree-node:hover { background: #f1f5f9; }
.tree-node.mod { background: #eef2ff; font-weight: 600; padding: var(--space-3); }
.tree-node.mod:hover { background: #e0e7ff; }
.tree-node.sub { padding-left: var(--space-5); font-weight: 500; color: #312e81; cursor: pointer; }
.tree-node.sub:hover { background: #eef2ff; }
.tree-node.kp { padding-left: var(--space-8); font-size: var(--font-size-sm); color: #475569; cursor: pointer; }
.tree-node.kp:hover { background: #eff6ff; }
.tree-node.mod .tree-name { cursor: pointer; }
.tree-node.mod .tree-name:hover { color: #4f46e5; }

/* 知识点简介弹窗 */
.kp-detail-tag { margin-bottom: 12px; }
.kp-detail-desc { font-size: 14px; line-height: 1.7; color: #475569; white-space: pre-wrap; }
.tree-arrow { color: #6366f1; transition: transform .2s; flex-shrink: 0; }
.tree-arrow.open { transform: rotate(90deg); }
.tree-dot { width: 6px; height: 6px; border-radius: 50%; background: #6366f1; flex-shrink: 0; }
.tree-name { flex: 1; font-size: var(--font-size-sm); }
.tree-count { font-size: 11px; color: var(--color-text-tertiary); }
.tree-children { border-top: 1px solid #e2e8f0; }
.tree-leaves { border-top: 1px dashed #e2e8f0; }

/* ── KP 操作按钮 ── */
.kp-actions { display: flex; gap: 2px; opacity: 0; transition: opacity .15s; flex-shrink: 0; }
.tree-node:hover .kp-actions { opacity: 1; }
.kp-btn {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border: none; border-radius: 4px;
  background: transparent; color: #64748b; cursor: pointer;
}
.kp-btn:hover { background: #eef2ff; color: #4f46e5; }
.kp-btn.danger:hover { background: #fef2f2; color: #ef4444; }
.course-detail { max-width:1180px; }
.detail-header { background:#fff; border:1px solid #e4e8e2; border-radius:18px; box-shadow:0 4px 16px rgba(15,23,42,.04); padding:28px 30px; }
.detail-title { letter-spacing:-.03em; }
.content-section { background:#fff; border:1px solid #e4e8e2; border-radius:16px; box-shadow:0 2px 8px rgba(15,23,42,.035); }
.section-title { letter-spacing:-.01em; }
.action-upload { background:#fff7ed; border-color:#fed7aa; }
.action-extract { background:#eff6ff; border-color:#bfdbfe; }
.action-progress { background:#eff6ff; border-color:#bfdbfe; }
.action-recommend { background:#ecfdf3; border-color:#bbf7d0; }
.action-quiz { background:#f5f3ff; border-color:#ddd6fe; }
.tree-node.mod { background:#f5f3ff; }
.tree-node.mod:hover { background:#ede9fe; }
.kp-item { background:#fbfcfa; border:1px solid #edf0eb; }
.doc-item { background:#fffbeb; border-color:#fde68a; }
.inline-empty { border-color:#cbd5e1; background:#fbfcfa; }
</style>
