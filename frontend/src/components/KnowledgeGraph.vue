<template>
  <div class="kg-container" ref="containerRef">
    <div v-if="!hasData" class="kg-empty">
      <div class="kg-empty-icon">🕸</div>
      <p class="kg-empty-title">暂无知识图谱数据</p>
      <p class="kg-empty-desc">上传文档并提取知识后，图谱将在此展示</p>
    </div>
    <div class="kg-scroll">
      <div v-show="hasData" ref="graphRef" class="kg-canvas"></div>
    </div>

    <!-- 关系图例 + 筛选 -->
    <div v-if="hasData" class="kg-legend">
      <div class="kg-legend-title">关系图例（点击筛选）</div>
      <div
        v-for="rel in legend"
        :key="rel.key"
        class="kg-legend-item"
        :class="{ off: !visibleRelations.includes(rel.key) }"
        @click="toggleRelation(rel.key)"
      >
        <span class="kg-legend-line" :style="{ background: rel.color }"></span>
        <span class="kg-legend-label">{{ rel.label }}</span>
      </div>
    </div>

    <div v-if="hasData" class="kg-toolbar">
      <button
        class="kg-layout-btn"
        :class="{ active: layoutMode === 'tree' }"
        @click="setLayoutMode('tree')"
      >树状图</button>
      <button
        class="kg-layout-btn"
        :class="{ active: layoutMode === 'radial' }"
        @click="setLayoutMode('radial')"
      >圆形图</button>
      <button
        class="kg-layout-btn"
        :class="{ active: showLeaves }"
        @click="toggleLeaves"
      >显示全部知识点</button>
      <div v-if="layoutMode === 'radial'" class="kg-gap-control">
        <span class="kg-gap-label">节点间距</span>
        <el-slider v-model="radialGap" :min="30" :max="160" :step="5" style="width: 120px" @change="buildGraph" />
      </div>
      <button class="kg-layout-btn" @click="fitGraph">适应画布</button>
      <button class="kg-export-btn" @click="exportImage" title="导出为PNG图片">
        <el-icon :size="16"><Download /></el-icon> 导出图片
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Graph } from '@antv/g6'
import { Download } from '@element-plus/icons-vue'
import type { GraphData } from '@/api/courses'

const props = defineProps<{
  data: GraphData | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'node-click', payload: { sqlite_id?: number; label: string; level?: number; is_module?: boolean; description?: string }): void
  (e: 'node-contextmenu', payload: { sqlite_id?: number; label: string; level?: number; is_module?: boolean }): void
}>()

const containerRef = ref<HTMLElement>()
const graphRef = ref<HTMLElement>()
let graphInstance: any = null

const hasData = ref(false)

let resizeObserver: ResizeObserver | undefined
let buildVersion = 0
const nodeScale = { value: 1 }

async function fitGraph() {
  await graphInstance?.fitView()
}

// 布局模式：tree=树状图, radial=圆形图
const layoutMode = ref<'tree' | 'radial'>('radial')
const radialGap = ref(80)

// 是否显示叶子知识点（默认只显示模块层级，避免节点过多挤成一团）
const showLeaves = ref(false)
function toggleLeaves() {
  showLeaves.value = !showLeaves.value
  buildGraph()
}

// 关系类型配置（与后端 relation 字段对应，后端返回大写，这里做归一化）
const RELATION_META: Record<string, { label: string; color: string }> = {
  prerequisite: { label: '先修关系', color: '#ea580c' },
  part_of: { label: '包含关系', color: '#16a34a' },
  related_to: { label: '相关关系', color: '#6366f1' },
}

const legend = [
  { key: 'prerequisite', label: '先修关系', color: '#ea580c' },
  { key: 'part_of', label: '包含关系', color: '#16a34a' },
  { key: 'related_to', label: '相关关系', color: '#6366f1' },
]

const visibleRelations = ref<string[]>(['prerequisite', 'part_of', 'related_to'])

function normalizeRelation(rel?: string): string {
  return (rel || '').toLowerCase()
}

function relColor(rel?: string): string {
  const meta = RELATION_META[normalizeRelation(rel)]
  return meta?.color || '#94a3b8'
}

function toggleRelation(key: string) {
  const idx = visibleRelations.value.indexOf(key)
  if (idx >= 0) {
    visibleRelations.value = visibleRelations.value.filter(k => k !== key)
  } else {
    visibleRelations.value = [...visibleRelations.value, key]
  }
  buildGraph()
}

function setLayoutMode(mode: 'tree' | 'radial') {
  if (layoutMode.value === mode) return
  layoutMode.value = mode
  buildGraph()
}

const NODE_COLORS = {
  fill: ['#bfdbfe', '#bbf7d0', '#fde68a', '#e9d5ff', '#bae6fd', '#fecdd3', '#fed7aa', '#d9f99d'],
  stroke: ['#2563eb', '#16a34a', '#d97706', '#7c3aed', '#0284c7', '#e11d48', '#ea580c', '#65a30d'],
}

function polarToXY(angle: number, radius: number, cx: number, cy: number) {
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) }
}

// 按子树权重分配扇区，逐层计算足以容纳节点和标签的半径。
// 缺失父节点、孤立节点及环形数据均作为独立分支，不叠放在圆心。
function computeRadialPositions(nodes: any[], cx: number, cy: number) {
  const byId = new Map(nodes.map(n => [String(n.id), n]))
  const children = new Map<string, string[]>()
  const parent = new Map<string, string>()
  for (const n of nodes) {
    const pid = n.parent_id
    if (pid != null && byId.has(String(pid)) && String(pid) !== String(n.id))
      parent.set(String(n.id), String(pid))
  }
  for (const e of props.data?.edges || []) {
    if (normalizeRelation(e.relation) === 'part_of' && byId.has(String(e.source))
        && byId.has(String(e.target)) && e.source !== e.target && !parent.has(String(e.source)))
      parent.set(String(e.source), String(e.target))
  }
  for (const [child, pid] of parent) {
    if (!children.has(pid)) children.set(pid, [])
    children.get(pid)!.push(child)
  }
  const seen = new Set<string>()
  type Branch = { id: string; weight: number; children: Branch[] }
  function visit(id: string): Branch | null {
    if (seen.has(id)) return null
    seen.add(id)
    const subs = (children.get(id) || []).map(visit).filter((v): v is Branch => v !== null)
    return { id, weight: Math.max(1, subs.reduce((sum, c) => sum + c.weight, 0)), children: subs }
  }
  const roots: Branch[] = []
  for (const n of nodes) if (!parent.has(String(n.id))) {
    const branch = visit(String(n.id))
    if (branch) roots.push(branch)
  }
  for (const n of nodes) {
    const branch = visit(String(n.id))
    if (branch) roots.push(branch)
  }
  const rings: { id: string; angle: number }[][] = []
  function place(branch: Branch, start: number, sweep: number, depth: number) {
    ;(rings[depth] ||= []).push({ id: branch.id, angle: start + sweep / 2 })
    let cursor = start
    for (const child of branch.children) {
      const part = sweep * child.weight / branch.weight
      place(child, cursor, part, depth + 1)
      cursor += part
    }
  }
  const total = roots.reduce((sum, r) => sum + r.weight, 0)
  let cursor = -Math.PI / 2
  for (const root of roots) {
    const sweep = 2 * Math.PI * root.weight / total
    place(root, cursor, sweep, 0)
    cursor += sweep
  }
  const positions = new Map<string, { x: number; y: number }>()
  let previousRadius = 0
  rings.forEach((ring, depth) => {
    let radius = depth === 0 ? 0 : previousRadius + 180 + radialGap.value
    if (ring.length > 1) {
      ring.forEach((node, i) => {
        const next = ring[(i + 1) % ring.length]!
        const delta = (next.angle - node.angle + Math.PI * 2) % (Math.PI * 2)
        // 标签限制为两行、每行约十字，预留包围盒对角线间距。
        radius = Math.max(radius, (180 + radialGap.value) / (2 * Math.sin(delta / 2)))
      })
    }
    for (const node of ring) positions.set(byId.get(node.id)!.id, polarToXY(node.angle, radius, cx, cy))
    previousRadius = radius
  })
  return positions
}

async function buildGraph() {
  const version = ++buildVersion
  if (!graphRef.value || !props.data) return
  if (!props.data.nodes?.length) {
    hasData.value = false
    graphInstance?.destroy()
    graphInstance = null
    return
  }

  hasData.value = true
  await nextTick()
  if (version !== buildVersion || !graphRef.value) return

  // 默认只显示模块层级（level 0/1），开启"显示全部知识点"后包含叶子（level 2）
  const visibleNodes = showLeaves.value
    ? props.data.nodes
    : props.data.nodes.filter((n: any) => (n as any).level !== 2)
  const visibleNodeIds = new Set(visibleNodes.map((n) => n.id))

  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }

  // 按筛选条件过滤边，且只保留两端节点都在的边
  const edges = (props.data.edges || []).filter((e) =>
    visibleRelations.value.includes(normalizeRelation(e.relation))
    && visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
  )

  // 按根模块分组，分配颜色索引（同一根模块下的节点同色，颜色数有限需取模）
  const rootColorIndex = new Map<string, number>()
  for (const n of visibleNodes) {
    const rid = (n as any).root_id || n.id
    if (!rootColorIndex.has(rid)) {
      rootColorIndex.set(rid, rootColorIndex.size % NODE_COLORS.fill.length)
    }
  }

  // 反转 PART_OF 边：让箭头从父指向子（根 → 子）
  const edgeList = edges.map((e) => {
    const rel = normalizeRelation(e.relation)
    const source = rel === 'part_of' ? e.target : e.source
    const target = rel === 'part_of' ? e.source : e.target
    return { source, target, data: { relation: rel } }
  })

  // 放射状布局：手动计算每个节点的位置（完整圆形，根在内、子在外）
  let manualPositions: Map<string, { x: number; y: number }> | null = null
  if (layoutMode.value === 'radial') {
    const w = graphRef.value.clientWidth || 800
    const h = graphRef.value.clientHeight || 500
    const cx = w / 2
    const cy = h / 2
    manualPositions = computeRadialPositions(visibleNodes, cx, cy)
  }

  const nodeList = visibleNodes.map((n, i) => {
    const rid = (n as any).root_id || n.id
    const pos = manualPositions?.get(n.id)
    return {
      id: n.id,
      data: {
        label: n.label,
        description: n.description || '',
        order: n.order_index ?? i,
        level: (n as any).level,
        is_module: (n as any).is_module,
        sqlite_id: (n as any).sqlite_id,
        root_id: rid,
        color_index: rootColorIndex.get(rid) ?? 0,
      },
      ...(pos ? { style: { x: pos.x, y: pos.y } } : {}),
    }
  })

  const data = { nodes: nodeList, edges: edgeList }

  graphInstance = new Graph({
    container: graphRef.value,
    data,
    width: graphRef.value.clientWidth,
    height: graphRef.value.clientHeight || 500,
    // 模块模式 1:1 居中显示（画布已按需求放大，容器内滚动）；全显模式缩放到视口
    autoFit: 'view',
    padding: 36,
    node: {
      style: {
        size: (d: any) => Math.max(24, Math.min(48, ((d.data?.label || d.id || '').length || 3) * 2 + 26)) * nodeScale.value,
        fill: (d: any) => NODE_COLORS.fill[d.data?.color_index ?? 0],
        stroke: (d: any) => NODE_COLORS.stroke[d.data?.color_index ?? 0],
        strokeWidth: 2,
        labelText: (d: any) => d.data?.label || d.id,
        labelFill: '#000000',
        labelFontSize: 13,
        labelWordWrap: true,
        labelMaxWidth: 140,
        labelMaxLines: 2,
        labelFontWeight: 500,
        labelFontFamily: 'PingFang SC, Microsoft YaHei, sans-serif',
        labelPlacement: 'bottom',
        labelOffsetY: 8,
      },
      state: {
        hover: {
          strokeWidth: 3,
          shadowBlur: 12,
          shadowColor: 'rgba(59,130,246,0.25)',
        },
      },
    },
    edge: {
      style: {
        stroke: (d: any) => relColor(d.data?.relation),
        strokeWidth: 2,
        lineDash: (d: any) => (d.data?.relation === 'related_to' ? [4, 4] : undefined),
        endArrow: true,
        endArrowOffset: 6,
      },
      state: {
        hover: { strokeWidth: 3.5 },
      },
    },
    ...(layoutMode.value === 'radial' ? {} : {
      layout: {
        type: 'dagre',
        rankdir: 'TB',
        nodesep: 150,
        ranksep: 120,
        sortByCombo: true,
      },
    }),
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'hover-activate'],
  })

  graphInstance.on('node:click', (evt: any) => {
    const id = evt?.target?.id
    const node = props.data?.nodes?.find((n) => n.id === id)
    if (node) {
      emit('node-click', {
        sqlite_id: (node as any).sqlite_id,
        label: node.label,
        level: (node as any).level,
        is_module: (node as any).is_module,
        description: node.description || '',
      })
    }
  })

  graphInstance.on('node:contextmenu', (evt: any) => {
    const id = evt?.target?.id
    const node = props.data?.nodes?.find((n) => n.id === id)
    if (node) {
      emit('node-contextmenu', {
        sqlite_id: (node as any).sqlite_id,
        label: node.label,
        level: (node as any).level,
        is_module: (node as any).is_module,
      })
    }
  })

  graphInstance.render()
}

watch(() => props.data, async () => {
  await nextTick()
  buildGraph()
}, { deep: true })

onMounted(() => {
  buildGraph()
  resizeObserver = new ResizeObserver(() => {
    if (!graphInstance || !graphRef.value) return
    const { clientWidth: width, clientHeight: height } = graphRef.value
    if (width > 0 && height > 0) graphInstance.setSize(width, height)
  })
  if (graphRef.value) resizeObserver.observe(graphRef.value)
})

async function exportImage() {
  if (!graphInstance) return
  try {
    // G6 v5 用 toDataURL 导出，mode: 'overall' 导出整个画布
    const dataURL = await graphInstance.toDataURL({ type: 'image/png', mode: 'overall' })
    // 叠加白色背景（G6 导出的 PNG 默认透明背景）
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0)
      const finalURL = canvas.toDataURL('image/png')
      const link = document.createElement('a')
      link.download = `knowledge-graph-${Date.now()}.png`
      link.href = finalURL
      link.click()
    }
    img.src = dataURL
  } catch (e) {
    console.error('导出图片失败:', e)
  }
}

onBeforeUnmount(() => { buildVersion++; resizeObserver?.disconnect(); graphInstance?.destroy() })
</script>

<style scoped>
.kg-container {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: 100%;
  width: 100%;
  min-height: 400px;
  border-radius: var(--radius-lg);
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  overflow: hidden;
}

.kg-scroll {
  width: 100%;
  order: 3;
  min-width: 0;
  overflow: hidden;
}

.kg-canvas {
  width: 100%;
  height: clamp(420px, 65vh, 760px);
}

.kg-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  gap: var(--space-2);
}

.kg-empty-icon { font-size: 42px; opacity: 0.4; margin-bottom: var(--space-3); }
.kg-empty-title { font-size: var(--font-size-md); font-weight: 600; color: var(--color-text-secondary); margin: 0; }
.kg-empty-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin: 0; }

.kg-toolbar {
  position: relative;
  padding: 10px 14px;
  flex-wrap: wrap;
  order: 2;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 10;
}

.kg-gap-control {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 4px 10px;
}

.kg-gap-label {
  font-size: 12px;
  color: #475569;
  white-space: nowrap;
}

.kg-layout-btn {
  padding: 6px 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  color: #475569;
  cursor: pointer;
  transition: all .15s;
}
.kg-layout-btn:hover { background: #f1f5f9; }
.kg-layout-btn.active {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
}
.kg-layout-btn.active:hover { background: #2563eb; }

.kg-export-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  color: #475569;
  cursor: pointer;
  transition: all .15s;
}
.kg-export-btn:hover { background: #f1f5f9; border-color: #94a3b8; }

.kg-legend {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  order: 1;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  z-index: 10;
  font-size: 12px;
  color: #475569;
}
.kg-legend-title { font-weight: 600; margin-bottom: 6px; }
.kg-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
  cursor: pointer;
  user-select: none;
  transition: opacity .15s;
}
.kg-legend-item.off { opacity: 0.35; }
.kg-legend-line { width: 20px; height: 3px; border-radius: 2px; display: inline-block; }
</style>
