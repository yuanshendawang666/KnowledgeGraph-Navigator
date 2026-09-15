<template>
  <Teleport to="body">
    <transition name="onboarding">
      <div v-if="modelValue" class="onboarding-mask">
        <section class="onboarding-panel" role="dialog" aria-modal="true" aria-label="个性化学习设置">
          <aside class="story-panel">
            <div class="brand-mark">知</div>
            <p class="eyebrow">为你定制学习内容</p>
            <h2>先认识你，<br><span>再推荐适合你的知识。</span></h2>
            <p class="story-copy">只需完成几项偏好选择。系统会结合知识图谱、学习进度与兴趣画像，为你调整推荐顺序和学习方法。</p>
            <div class="profile-preview">
              <span v-for="item in previewTags" :key="item">{{ item }}</span>
              <span v-if="!previewTags.length" class="placeholder-tag">你的偏好将在这里汇聚</span>
            </div>
            <div class="privacy-note"><span>✓</span> 画像仅用于本系统的学习推荐</div>
          </aside>

          <main class="choice-panel">
            <header class="step-header">
              <div>
                <span class="step-count">0{{ step }} / 03</span>
                <h3>{{ stepTitle }}</h3>
                <p>{{ stepDescription }}</p>
              </div>
              <div class="step-dots" aria-hidden="true">
                <i v-for="n in 3" :key="n" :class="{ active: n <= step }"></i>
              </div>
            </header>

            <div v-if="step === 1" class="option-grid age-grid">
              <button v-for="item in ageOptions" :key="item.value" type="button" class="option-card"
                :class="{ selected: form.age_range === item.value }" @click="form.age_range = item.value">
                <span class="option-index">{{ item.index }}</span>
                <strong>{{ item.value }}</strong>
                <small>{{ item.note }}</small>
              </button>
            </div>

            <div v-else-if="step === 2" class="interest-wrap">
              <p class="selection-tip">可多选，建议选择 3–6 项</p>
              <div class="interest-grid">
                <button v-for="item in interestOptions" :key="item.name" type="button" class="interest-card"
                  :class="{ selected: form.interests.includes(item.name) }" @click="toggle(form.interests, item.name, 6)">
                  <span class="interest-icon">{{ item.icon }}</span>
                  <span><strong>{{ item.name }}</strong><small>{{ item.note }}</small></span>
                  <b class="check">✓</b>
                </button>
              </div>
            </div>

            <div v-else class="preference-layout">
              <div class="goal-block">
                <label>你目前最关注什么？</label>
                <div class="goal-list">
                  <button v-for="goal in goalOptions" :key="goal" type="button"
                    :class="{ selected: form.learning_goal === goal }" @click="form.learning_goal = goal">{{ goal }}</button>
                </div>
              </div>
              <div class="goal-block">
                <label>你更喜欢怎样学习？ <em>可多选</em></label>
                <div class="format-grid">
                  <button v-for="item in preferenceOptions" :key="item.name" type="button"
                    :class="{ selected: form.content_preferences.includes(item.name) }"
                    @click="toggle(form.content_preferences, item.name, 4)">
                    <span>{{ item.icon }}</span><strong>{{ item.name }}</strong><small>{{ item.note }}</small>
                  </button>
                </div>
              </div>
            </div>

            <footer class="panel-footer">
              <button v-if="step > 1" type="button" class="back-btn" @click="step--">上一步</button>
              <span v-else></span>
              <button type="button" class="next-btn" :disabled="!canContinue || saving" @click="next">
                {{ saving ? '正在生成画像…' : step === 3 ? '开启个性化学习' : '继续' }}
                <span>→</span>
              </button>
            </footer>
          </main>
        </section>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; completed: [] }>()
const auth = useAuthStore()
const step = ref(1)
const saving = ref(false)
const form = reactive({ age_range: '', interests: [] as string[], learning_goal: '', content_preferences: [] as string[] })

const ageOptions = [
  { index: 'A', value: '12岁以下', note: '启蒙与兴趣探索' }, { index: 'B', value: '12–15岁', note: '初中学习阶段' },
  { index: 'C', value: '16–18岁', note: '高中学习阶段' }, { index: 'D', value: '19–22岁', note: '大学学习阶段' },
  { index: 'E', value: '23岁以上', note: '职业与自主提升' },
]
const interestOptions = [
  { icon: '</>', name: '编程开发', note: '语言、算法与项目实践' }, { icon: 'AI', name: '人工智能', note: '模型、数据与智能应用' },
  { icon: '∑', name: '数学逻辑', note: '推理、计算与建模' }, { icon: '◉', name: '数据分析', note: '洞察、可视化与决策' },
  { icon: '⚙', name: '工程实践', note: '动手实现与系统设计' }, { icon: '✦', name: '创新竞赛', note: '项目、答辩与成果展示' },
  { icon: '文', name: '人文阅读', note: '表达、写作与通识' }, { icon: '⌁', name: '科学探索', note: '自然科学与实验发现' },
]
const goalOptions = ['夯实基础', '课程提分', '技能提升', '竞赛准备', '项目实践', '兴趣探索']
const preferenceOptions = [
  { icon: '▤', name: '图文讲解', note: '结构清晰、便于回顾' }, { icon: '▶', name: '案例演示', note: '从实例中理解概念' },
  { icon: '✓', name: '练习巩固', note: '边学边练、及时反馈' }, { icon: '◇', name: '路径学习', note: '按先修关系逐步推进' },
]

const stepTitle = computed(() => ['你正处于哪个学习阶段？', '哪些内容更能激发你的兴趣？', '最后，告诉我们你的学习方式'][step.value - 1])
const stepDescription = computed(() => ['用于匹配合适的内容难度与表达方式', '你的选择会参与知识点排序与课程推荐', '目标和内容偏好将影响推荐理由与学习方法'][step.value - 1])
const canContinue = computed(() => step.value === 1 ? !!form.age_range : step.value === 2 ? form.interests.length > 0 : !!form.learning_goal && form.content_preferences.length > 0)
const previewTags = computed(() => [form.age_range, ...form.interests.slice(0, 3), form.learning_goal].filter(Boolean))

watch(() => props.modelValue, (open) => {
  if (!open) return
  step.value = 1
  form.age_range = auth.user?.age_range || ''
  form.interests = [...(auth.user?.interests || [])]
  form.learning_goal = auth.user?.learning_goal || ''
  form.content_preferences = [...(auth.user?.content_preferences || [])]
}, { immediate: true })

function toggle(list: string[], value: string, max: number) {
  const index = list.indexOf(value)
  if (index >= 0) list.splice(index, 1)
  else if (list.length < max) list.push(value)
  else ElMessage.info(`最多选择 ${max} 项`)
}

async function next() {
  if (!canContinue.value) return
  if (step.value < 3) { step.value++; return }
  saving.value = true
  try {
    await auth.updateProfile({ ...form, onboarding_completed: true })
    ElMessage.success('专属学习画像已生成')
    emit('update:modelValue', false)
    emit('completed')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存偏好失败，请稍后重试')
  } finally { saving.value = false }
}
</script>

<style scoped>
.onboarding-mask{position:fixed;inset:0;z-index:4000;display:grid;place-items:center;padding:28px;background:rgba(9,21,40,.66);backdrop-filter:blur(14px)}
.onboarding-panel{width:min(1080px,96vw);height:min(700px,92vh);display:grid;grid-template-columns:38% 62%;overflow:hidden;border:1px solid rgba(255,255,255,.75);border-radius:30px;background:#f8fbff;box-shadow:0 34px 100px rgba(5,20,45,.32)}
.story-panel{position:relative;display:flex;flex-direction:column;padding:54px 44px;color:#fff;background:linear-gradient(155deg,#0b3b79 0%,#0b69b4 55%,#0f9f91 125%);overflow:hidden}
.story-panel:before,.story-panel:after{content:"";position:absolute;border:1px solid rgba(255,255,255,.14);border-radius:50%}.story-panel:before{width:360px;height:360px;right:-190px;top:-80px}.story-panel:after{width:280px;height:280px;left:-170px;bottom:-110px}
.brand-mark{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:#fff;color:#0b5ca8;font-size:23px;font-weight:900;box-shadow:0 10px 28px rgba(0,0,0,.16)}
.eyebrow{margin:52px 0 12px;font-size:13px;font-weight:800;letter-spacing:.16em;color:#9eeadd}.story-panel h2{margin:0;font-family:"Microsoft YaHei UI","Noto Sans SC",sans-serif;font-size:36px;line-height:1.35;letter-spacing:-.04em}.story-panel h2 span{color:#bdf5e8}.story-copy{margin:24px 0 30px;color:rgba(255,255,255,.78);font-size:15px;line-height:1.9}
.profile-preview{display:flex;flex-wrap:wrap;gap:9px;min-height:78px;padding:15px;border:1px solid rgba(255,255,255,.14);border-radius:18px;background:rgba(255,255,255,.08)}.profile-preview span{height:30px;padding:5px 11px;border-radius:999px;background:rgba(255,255,255,.16);font-size:12px}.profile-preview .placeholder-tag{background:transparent;color:rgba(255,255,255,.5)}.privacy-note{display:flex;gap:8px;align-items:center;margin-top:auto;color:rgba(255,255,255,.68);font-size:12px}.privacy-note span{color:#83f0d5}
.choice-panel{display:flex;min-width:0;flex-direction:column;padding:46px 50px 36px}.step-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:30px}.step-count{font-family:Georgia,serif;font-size:13px;font-weight:700;color:#0b69b4}.step-header h3{margin:8px 0 7px;color:#10233f;font-size:27px;letter-spacing:-.04em}.step-header p{margin:0;color:#718096;font-size:13px}.step-dots{display:flex;gap:7px;margin-top:8px}.step-dots i{width:22px;height:5px;border-radius:5px;background:#dbe6f1;transition:.25s}.step-dots i.active{width:34px;background:#0f8d82}
.option-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.option-card{position:relative;display:grid;grid-template-columns:42px 1fr;grid-template-rows:auto auto;gap:2px 12px;text-align:left;padding:19px;border:1px solid #dce6ef;border-radius:17px;background:#fff;color:#14243d;cursor:pointer;transition:.2s}.option-card:hover{transform:translateY(-2px);border-color:#86b8dd;box-shadow:0 9px 24px rgba(24,87,138,.09)}.option-card.selected{border-color:#0f8d82;background:#eefbf8;box-shadow:inset 0 0 0 1px #0f8d82}.option-index{grid-row:1/3;display:grid;place-items:center;width:40px;height:40px;border-radius:12px;background:#edf4fb;color:#236da8;font:700 16px Georgia}.option-card.selected .option-index{background:#0f8d82;color:#fff}.option-card strong{font-size:15px}.option-card small{color:#8795a8}
.selection-tip{margin:-11px 0 12px;color:#8a98aa;font-size:12px}.interest-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.interest-card{position:relative;display:flex;align-items:center;gap:12px;padding:13px 15px;text-align:left;border:1px solid #dce6ef;border-radius:15px;background:#fff;cursor:pointer;transition:.18s}.interest-card:hover{border-color:#8ab9d9}.interest-card.selected{border-color:#167eac;background:#f0f9fd}.interest-icon{display:grid;place-items:center;width:40px;height:40px;border-radius:12px;color:#0a6e9d;background:#e5f4fb;font-weight:800}.interest-card strong,.interest-card small{display:block}.interest-card strong{color:#172942;font-size:14px}.interest-card small{margin-top:4px;color:#8997a8;font-size:11px}.check{position:absolute;right:12px;top:10px;display:none;color:#0d978a}.interest-card.selected .check{display:block}
.preference-layout{display:grid;gap:25px}.goal-block label{display:block;margin-bottom:12px;color:#20324b;font-weight:800}.goal-block label em{font-style:normal;font-weight:400;color:#8a98aa;font-size:12px}.goal-list{display:flex;flex-wrap:wrap;gap:9px}.goal-list button{padding:9px 15px;border:1px solid #d8e2ec;border-radius:999px;background:#fff;color:#526378;cursor:pointer}.goal-list button.selected{border-color:#0f8d82;background:#e9f9f5;color:#087267;font-weight:700}.format-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.format-grid button{display:grid;grid-template-columns:32px 1fr;grid-template-rows:auto auto;padding:13px;text-align:left;border:1px solid #dce6ef;border-radius:14px;background:#fff;cursor:pointer}.format-grid button>span{grid-row:1/3;color:#177ca9;font-size:20px}.format-grid strong{font-size:13px;color:#21334c}.format-grid small{color:#8b98a8}.format-grid button.selected{border-color:#167eac;background:#eef9fd}
.panel-footer{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding-top:24px}.back-btn,.next-btn{border:0;cursor:pointer;font-weight:800}.back-btn{padding:12px;background:transparent;color:#718096}.next-btn{display:flex;align-items:center;gap:20px;padding:13px 19px 13px 23px;border-radius:13px;background:#0d2748;color:#fff;box-shadow:0 10px 22px rgba(13,39,72,.2)}.next-btn span{font-size:20px}.next-btn:disabled{opacity:.38;cursor:not-allowed;box-shadow:none}
.onboarding-enter-active,.onboarding-leave-active{transition:.3s}.onboarding-enter-from,.onboarding-leave-to{opacity:0}.onboarding-enter-from .onboarding-panel{transform:translateY(20px) scale(.98)}
@media(max-width:780px){.onboarding-mask{padding:10px}.onboarding-panel{height:96vh;grid-template-columns:1fr}.story-panel{display:none}.choice-panel{padding:28px 20px}.option-grid,.interest-grid,.format-grid{grid-template-columns:1fr}.choice-panel{overflow:auto}.step-header h3{font-size:23px}}
</style>
