<template>
  <div class="practice-home">
    <header class="home-header">
      <div><h1>在线练习</h1><p>选择一门课程，开始巩固知识点</p></div>
    </header>
    <div v-if="loading" class="loading">正在加载课程…</div>
    <div v-else-if="!courses.length" class="empty">暂无可练习课程</div>
    <div v-else class="course-grid">
      <article v-for="course in courses" :key="course.id" class="course-card">
        <div class="course-icon">练</div>
        <div class="course-main"><h2>{{ course.title }}</h2><p>{{ course.description || '根据知识点生成个性化练习' }}</p></div>
        <el-button type="primary" @click="router.push(`/course/${course.id}/practice`)">开始练习<el-icon><ArrowRight /></el-icon></el-button>
      </article>
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { coursesAPI, type CourseItem } from '@/api/courses'
const router=useRouter(); const courses=ref<CourseItem[]>([]); const loading=ref(true)
onMounted(async()=>{try{courses.value=await coursesAPI.getList()}finally{loading.value=false}})
</script>
<style scoped>
.practice-home{max-width:980px;margin:0 auto}.home-header{margin-bottom:26px}.home-header h1{margin:0;color:#172554;font-size:30px}.home-header p{margin:8px 0 0;color:#64748b}.course-grid{display:grid;gap:16px}.course-card{display:flex;align-items:center;gap:16px;padding:20px 22px;border:1px solid #cbd5e1;border-left:5px solid #db2777;border-radius:16px;background:#fff;box-shadow:0 6px 18px rgba(15,23,42,.06)}.course-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:14px;background:#fce7f3;color:#be185d;font-weight:700}.course-main{flex:1}.course-main h2{margin:0;color:#334155;font-size:18px}.course-main p{margin:6px 0 0;color:#94a3b8;font-size:13px}.loading,.empty{padding:70px;text-align:center;color:#94a3b8;background:#fff;border-radius:16px}
</style>
