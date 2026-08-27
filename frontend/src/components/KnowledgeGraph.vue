<template>
  <div class="kg-container" ref="containerRef">
    <div v-if="!hasData" class="kg-empty">
      <div class="kg-empty-icon">🕸</div>
      <p class="kg-empty-title">暂无知识图谱数据</p>
      <p class="kg-empty-desc">上传文档并提取知识后，图谱将在此展示</p>
    </div>
    <div v-show="hasData" ref="graphRef" class="kg-canvas"></div>

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

// 布局模式：tree=树状图, radial=圆形图
const layoutMode = ref<'tree' | 'radial'>('tree')

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

function buildGraph() {
  if (!graphRef.value || !props.data) return
  if (!props.data.nodes?.length) {
    hasData.value = false
    return
  }

  hasData.value = true

  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }

  // 按筛选条件过滤边
  const edges = (props.data.edges || []).filter((e) =>
    visibleRelations.value.includes(normalizeRelation(e.relation))
  )

  // 按根模块分组，分配颜色索引（同一根模块下的节点同色）
  const rootColorIndex = new Map<string, number>()
  for (const n of props.data.nodes) {
    const rid = (n as any).root_id || n.id
    if (!rootColorIndex.has(rid)) {
      rootColorIndex.set(rid, rootColorIndex.size)
    }
  }

  const data = {
    nodes: props.data.nodes.map((n, i) => {
      const rid = (n as any).root_id || n.id
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
      }
    }),
    edges: edges.map((e) => ({
      source: e.source,
      target: e.target,
      data: {
        relation: normalizeRelation(e.relation),
      },
    })),
  }

  graphInstance = new Graph({
    container: graphRef.value,
    data,
    width: graphRef.value.clientWidth,
    height: graphRef.value.clientHeight || 500,
    autoFit: 'view',
    node: {
      style: {
        size: (d: any) => Math.max(30, Math.min(48, ((d.data?.label || d.id || '').length || 3) * 2 + 26)),
        fill: (d: any) => NODE_COLORS.fill[d.data?.color_index ?? 0],
        stroke: (d: any) => NODE_COLORS.stroke[d.data?.color_index ?? 0],
        strokeWidth: 2,
        labelText: (d: any) => d.data?.label || d.id,
        labelFill: '#ffffff',
        labelFontSize: 12,
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
      },
      state: {
        hover: { strokeWidth: 3.5 },
      },
    },
    layout: layoutMode.value === 'radial'
      ? { type: 'concentric', sortBy: (d: any) => (2 - (d.data?.level ?? 2)), preventOverlap: true }
      : {
          type: 'dagre',
          rankdir: 'TB',
          nodesep: 30,
          ranksep: 60,
          sortByCombo: true,
        },
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

onMounted(() => { buildGraph() })

async function exportImage() {
  if (!graphInstance) return
  try {
    // G6 v5 用 toDataURL 导出，mode: 'overall' 导出整个画布
    const dataURL = await graphInstance.toDataURL({ type: 'image/png', mode: 'overall' })
    const link = document.createElement('a')
    link.download = `knowledge-graph-${Date.now()}.png`
    link.href = dataURL
    link.click()
  } catch (e) {
    console.error('导出图片失败:', e)
  }
}

onBeforeUnmount(() => { graphInstance?.destroy() })
</script>

<style scoped>
.kg-container {
  position: relative;
  width: 100%;
  min-height: 400px;
  border-radius: var(--radius-lg);
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  overflow: hidden;
}

.kg-canvas {
  width: 100%;
  height: 100%;
  min-height: 460px;
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
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  z-index: 10;
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
  position: absolute;
  top: 8px;
  left: 8px;
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
