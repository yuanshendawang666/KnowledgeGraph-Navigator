<template>
  <div class="auth-view">
    <div class="auth-card">
      <div class="auth-header">
        <img src="/logo.png" alt="知谱智航" class="auth-logo" />
        <h1 class="auth-title">创建账号</h1>
        <p class="auth-subtitle">加入知谱智航，开启知识学习之旅</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="2-32 个字符"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="form.email"
            placeholder="your@email.com"
            :prefix-icon="Message"
            size="large"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="至少 6 个字符"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item label="重复密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item label="身份" prop="role">
          <el-radio-group v-model="form.role" class="role-group">
            <el-radio-button value="student">学生</el-radio-button>
            <el-radio-button value="teacher">教师</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="auth-submit"
            @click="handleRegister"
          >
            {{ loading ? '注册中…' : '注 册' }}
          </el-button>
        </el-form-item>
      </el-form>

      <p class="auth-switch">
        已有账号？
        <router-link to="/login">立即登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  role: 'student',
})

const validateConfirmPassword = (_rule: any, value: string, callback: Function) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 32, message: '用户名长度在 2 到 32 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度至少 6 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
  role: [
    { required: true, message: '请选择身份', trigger: 'change' },
  ],
}

async function handleRegister() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.register({
      username: form.username,
      email: form.email,
      password: form.password,
      role: form.role,
    })
    ElMessage.success('注册成功')
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
  max-width: 440px;
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

.role-group {
  width: 100%;
  display: flex;
}

.role-group :deep(.el-radio-button) {
  flex: 1;
}

.role-group :deep(.el-radio-button__inner) {
  width: 100%;
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
}

.auth-switch a:hover {
  color: var(--color-brand-500);
}
</style>
