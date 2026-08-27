<template>
  <div class="auth-view">
    <div class="auth-card">
      <div class="auth-header">
        <img src="/logo.png" alt="知谱智航" class="auth-logo" />
        <h1 class="auth-title">知谱智航</h1>
        <p class="auth-subtitle">知识图谱智能教学平台</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
            autocomplete="username"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            autocomplete="current-password"
            @keydown.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="auth-submit"
            @click="handleLogin"
          >
            {{ loading ? '登录中…' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <p class="auth-switch">
        还没有账号？
        <router-link to="/register">立即注册</router-link>
      </p>
    </div>

    <p class="auth-footer-text">基于 DeepSeek 大模型的知识图谱智能教学系统</p>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 32, message: '用户名长度在 2 到 32 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度至少 6 个字符', trigger: 'blur' },
  ],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: var(--space-6);
  background:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(99, 102, 241, 0.06), transparent),
    var(--color-surface-overlay);
}

.auth-card {
  width: 100%;
  max-width: 400px;
  padding: var(--space-10) var(--space-8);
  background: var(--color-surface-default);
  border: 1px solid var(--color-border-subtle);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
}

.auth-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.auth-logo {
  width: 52px;
  height: 52px;
  display: block;
  margin: 0 auto var(--space-3);
  object-fit: contain;
}

.auth-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-text-primary);
  margin: 0 0 var(--space-1);
}

.auth-subtitle {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin: 0;
}

.auth-submit {
  width: 100%;
  margin-top: var(--space-2);
}

.auth-switch {
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: var(--space-6) 0 0;
}

.auth-switch a {
  color: var(--color-brand-600);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--duration-fast);
}

.auth-switch a:hover {
  color: var(--color-brand-500);
}

.auth-footer-text {
  margin-top: var(--space-8);
  font-size: var(--font-size-xs);
  color: var(--color-text-placeholder);
}
</style>
