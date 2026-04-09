<template>
  <div class="login-page">
    <!-- 用 img + object-fit 铺满视口，略好于 background 拉伸；更清晰请换 ≥1920px 宽图 -->
    <img class="login-bg-img" src="/login-bg.png" alt="" decoding="async" fetchpriority="high" />
    <div class="login-overlay" />
    <div class="login-inner">
      <div class="login-form-wrap">
        <div class="login-logo" aria-hidden="true">
          <!-- 食迅易联：六边形底座 + 三结互联（链路与协同）+ 中心核（AI） -->
          <svg class="login-logo__svg" viewBox="0 0 56 56" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="sxylLogoGrad" x1="6" y1="10" x2="50" y2="48" gradientUnits="userSpaceOnUse">
                <stop stop-color="#67e8f9" />
                <stop offset="0.45" stop-color="#38bdf8" />
                <stop offset="1" stop-color="#2563eb" />
              </linearGradient>
            </defs>
            <path
              class="login-logo__hex"
              d="M28 4.5 47.5 15.75v24.5L28 51.5 8.5 40.25v-24.5L28 4.5z"
              fill="rgba(56,189,248,0.12)"
              stroke="url(#sxylLogoGrad)"
              stroke-width="1.35"
              stroke-linejoin="round"
            />
            <path
              class="login-logo__arc"
              d="M18 22c4-6 16-6 20 0"
              fill="none"
              stroke="url(#sxylLogoGrad)"
              stroke-width="1.35"
              stroke-linecap="round"
            />
            <path
              class="login-logo__arc2"
              d="M18 34c4 6 16 6 20 0"
              fill="none"
              stroke="url(#sxylLogoGrad)"
              stroke-width="1.35"
              stroke-linecap="round"
              opacity="0.85"
            />
            <circle cx="28" cy="19" r="3.2" fill="url(#sxylLogoGrad)" />
            <circle cx="17.5" cy="36.5" r="3" fill="url(#sxylLogoGrad)" opacity="0.95" />
            <circle cx="38.5" cy="36.5" r="3" fill="url(#sxylLogoGrad)" opacity="0.95" />
            <circle cx="28" cy="28" r="5" fill="none" stroke="url(#sxylLogoGrad)" stroke-width="1.25" opacity="0.9" />
            <circle cx="28" cy="28" r="1.9" fill="#e0f2fe" opacity="0.95" />
          </svg>
        </div>
        <h1 class="login-title">欢迎进入食迅易联AI平台</h1>
        <div class="login-fields">
          <el-input
            v-model="username"
            placeholder="账号"
            class="login-input login-input--line"
            :prefix-icon="User"
            autocomplete="username"
          />
          <div class="pwd-row">
            <el-input
              v-model="password"
              type="password"
              placeholder="密码"
              class="login-input login-input--line login-input--pwd"
              :prefix-icon="Lock"
              show-password
              autocomplete="current-password"
              @keyup.enter="submit"
            />
            <el-link type="info" :underline="false" class="forgot-link" @click="onForgot">
              忘记密码？
            </el-link>
          </div>
        </div>
        <el-button type="primary" class="login-btn" size="large" :loading="loading" @click="submit">
          登录
        </el-button>
      </div>
    </div>
    <footer class="login-footer">Copyright © 北京食迅易联信息技术有限公司</footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { setLoggedIn } from '../utils/authSession'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

function onForgot() {
  ElMessage.info('请联系管理员重置密码')
}

function submit() {
  loading.value = true
  setLoggedIn()
  const raw = route.query.redirect
  const target = typeof raw === 'string' && raw.startsWith('/') ? raw : '/'
  router
    .replace(target)
    .catch(() => {})
    .finally(() => {
      loading.value = false
    })
}
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  margin: 0;
  padding: 0;
  background-color: #0a0e14;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.login-bg-img {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  object-fit: cover;
  object-position: center;
  z-index: 0;
  pointer-events: none;
  user-select: none;
}

.login-overlay {
  position: fixed;
  inset: 0;
  z-index: 1;
  background: linear-gradient(
    105deg,
    rgba(10, 14, 20, 0.82) 0%,
    rgba(10, 14, 20, 0.45) 42%,
    rgba(10, 14, 20, 0.15) 100%
  );
  pointer-events: none;
}

.login-inner {
  position: relative;
  z-index: 2;
  padding: 48px 64px 80px;
  max-width: 520px;
}

.login-form-wrap {
  max-width: 320px;
}

.login-logo {
  width: 64px;
  height: 64px;
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(30, 58, 90, 0.45), rgba(15, 23, 42, 0.65));
  border: 1px solid rgba(74, 217, 255, 0.4);
  box-shadow:
    0 0 28px rgba(56, 189, 248, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28px;
  padding: 6px;
}

.login-logo__svg {
  width: 46px;
  height: 46px;
  display: block;
  filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.35));
}

.login-title {
  font-size: 22px;
  font-weight: 600;
  color: #f1f5f9;
  letter-spacing: 0.02em;
  margin: 0 0 36px;
  line-height: 1.35;
}

.login-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 28px;
}

.pwd-row {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.forgot-link {
  font-size: 12px;
  color: rgba(203, 213, 225, 0.65) !important;
}

.forgot-link:hover {
  color: #4ad9ff !important;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  border-radius: 4px;
  background: linear-gradient(90deg, #1e6fd9, #3a86ff);
  border: none;
  box-shadow: 0 4px 20px rgba(58, 134, 255, 0.35);
}

.login-btn:hover {
  filter: brightness(1.06);
}

.login-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 3;
  text-align: center;
  padding: 16px;
  font-size: 12px;
  color: rgba(203, 213, 225, 0.55);
}

/* 下划线输入：去白底，仅保留下边框 */
:deep(.login-input--line .el-input__wrapper) {
  background: transparent;
  box-shadow: none;
  border: none;
  border-radius: 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.45);
  padding-left: 0;
  padding-bottom: 4px;
  transition: border-color 0.2s;
}

:deep(.login-input--line .el-input__wrapper:hover),
:deep(.login-input--line .el-input__wrapper.is-focus) {
  box-shadow: none;
  border-bottom-color: rgba(74, 217, 255, 0.75);
}

:deep(.login-input--line .el-input__inner) {
  color: #f1f5f9;
}

:deep(.login-input--line .el-input__inner::placeholder) {
  color: rgba(148, 163, 184, 0.7);
}

:deep(.login-input--line .el-input__prefix) {
  color: rgba(148, 163, 184, 0.85);
}

:deep(.login-input--pwd .el-input__wrapper) {
  padding-right: 28px;
}
</style>
