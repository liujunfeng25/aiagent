<template>
  <el-config-provider :locale="zhCn">
    <router-view v-if="isPublicLayout" class="public-route-view" />
    <el-container v-else class="layout">
      <TechParticleBg class="app-tech-bg" />
      <el-aside width="220px" class="sidebar">
        <div class="logo">
          <span class="logo__dot" />
          <div class="logo__text">
            <strong>AI Agent</strong>
            <small>INTELLIGENCE PLATFORM</small>
          </div>
        </div>
        <el-menu :default-active="$route.path" router>
          <el-sub-menu index="grp-workbench">
            <template #title>
              <span class="menu-group">AI工作台</span>
            </template>
            <el-menu-item index="/" title="平台概览与核心运营状态">
              <el-icon><Odometer /></el-icon>
              <span>工作台</span>
            </el-menu-item>
            <el-menu-item index="/cockpit" title="北京市冷链车辆与数据大屏（演示数据）">
              <el-icon><Monitor /></el-icon>
              <span>数据驾驶舱</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="grp-data-train">
            <template #title>
              <span class="menu-group">数据与训练</span>
            </template>
            <el-menu-item index="/datasets" title="训练用图片数据集，与业务库分析无关">
              <el-icon><Folder /></el-icon>
              <span>数据集</span>
            </el-menu-item>
            <el-menu-item index="/categories" title="按类别文件夹管理图片，可一键参与训练">
              <el-icon><Collection /></el-icon>
              <span>类别管理</span>
            </el-menu-item>
            <el-menu-item index="/training" title="使用数据集或类别目录训练分类模型">
              <el-icon><VideoPlay /></el-icon>
              <span>训练管理</span>
            </el-menu-item>
            <el-menu-item index="/models">
              <el-icon><Box /></el-icon>
              <span>模型库</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="grp-intelligent-app">
            <template #title>
              <span class="menu-group">智能应用</span>
            </template>
            <el-menu-item index="/recognition" title="图像分类识别（货品是哪一类）">
              <el-icon><PictureFilled /></el-icon>
              <span>识别中心</span>
            </el-menu-item>
            <el-menu-item index="/documents" title="送货单等表格 OCR 与双单对比">
              <el-icon><Document /></el-icon>
              <span>票据识别</span>
            </el-menu-item>
            <el-menu-item index="/insights" title="订单与销售、新发地行情、缺货背单、库内价格指数（近一年）">
              <el-icon><DataAnalysis /></el-icon>
              <span>数据洞察</span>
            </el-menu-item>
            <el-menu-item index="/price">
              <el-icon><TrendCharts /></el-icon>
              <span>报价抓取</span>
            </el-menu-item>
            <el-menu-item index="/logistics">
              <el-icon><Van /></el-icon>
              <span>智能物流</span>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="grp-governance">
            <template #title>
              <span class="menu-group">系统治理</span>
            </template>
            <el-menu-item index="/system">
              <el-icon><Setting /></el-icon>
              <span>系统管理</span>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="header">
          <span class="title">AI 训练与数据智能平台</span>
        </el-header>
        <el-main :class="['main', { 'main--full-bleed': route.meta.fullBleed }]">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import {
  Monitor,
  Odometer,
  Folder,
  Collection,
  VideoPlay,
  Box,
  PictureFilled,
  Document,
  DataAnalysis,
  TrendCharts,
  Setting,
  Van,
} from '@element-plus/icons-vue'
import TechParticleBg from './components/cockpit/TechParticleBg.vue'

const route = useRoute()
const isPublicLayout = computed(() => route.meta.public === true)
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html {
  overflow-x: hidden;
}
html, body {
  height: 100%;
  margin: 0;
}
#app {
  min-height: 100%;
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  /* 业务区略抬亮度；登录页自身全屏背景会盖住 */
  background: linear-gradient(165deg, #172554 0%, #1e3a5f 42%, #152042 100%);
}
:root {
  --ai-color-primary: #1e90ff;
  --ai-color-secondary: #22d3ee;
  --ai-color-accent: #7c3aed;
  --ai-color-success: #34d399;
  --ai-color-warning: #f59e0b;
  --ai-color-danger: #f87171;
  --ai-bg-panel: rgba(30, 41, 72, 0.82);
  --ai-border-glow: rgba(56, 189, 248, 0.4);
  --ai-text-primary: #f1f5f9;
  --ai-text-secondary: rgba(203, 213, 225, 0.92);
}
/* 登录等公开页：与 #app 同高，避免四周露出灰边 */
.public-route-view {
  display: block;
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
}
.layout {
  height: 100%;
  position: relative;
  overflow: hidden;
}
.app-tech-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.62;
  mix-blend-mode: screen;
}
.layout > .el-container,
.layout > .el-aside {
  position: relative;
  z-index: 1;
}
.sidebar {
  background:
    linear-gradient(180deg, rgba(2, 10, 30, 0.92), rgba(1, 21, 53, 0.96));
  border-right: 1px solid rgba(30, 144, 255, 0.24);
  backdrop-filter: blur(4px);
}
.logo {
  padding: 14px 14px 10px;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo__dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #67e8f9 0%, #1e90ff 65%, #0a66c2 100%);
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.7);
}
.logo__text strong {
  display: block;
  font-size: 16px;
  line-height: 1.1;
}
.logo__text small {
  display: block;
  margin-top: 2px;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: rgba(148, 163, 184, 0.85);
}
.el-menu { border: none; background: transparent; }
.menu-group {
  color: rgba(203, 213, 225, 0.92);
  font-size: 12px;
  letter-spacing: 0.08em;
}
.el-sub-menu :deep(.el-sub-menu__title) {
  color: rgba(203, 213, 225, 0.88);
  background: rgba(255, 255, 255, 0.02);
}
.el-menu-item {
  color: rgba(241, 245, 249, 0.94);
  margin: 2px 8px;
  border-radius: 8px;
}
.el-menu-item:hover, .el-menu-item.is-active {
  color: #fff;
  background: linear-gradient(90deg, rgba(30, 144, 255, 0.24), rgba(34, 211, 238, 0.14));
}
.header {
  background: linear-gradient(90deg, rgba(7, 18, 43, 0.9), rgba(8, 27, 58, 0.85));
  border-bottom: 1px solid var(--ai-border-glow);
  box-shadow: 0 1px 4px rgba(0,0,0,.15);
  display: flex;
  align-items: center;
  padding: 0 24px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ai-text-primary);
}
.main {
  background:
    radial-gradient(ellipse 100% 70% at 50% 0%, rgba(56, 189, 248, 0.09), transparent 55%),
    linear-gradient(180deg, rgba(30, 58, 90, 0.22) 0%, rgba(15, 23, 42, 0.35) 100%);
  padding: 24px;
  min-height: calc(100vh - 60px);
}
.main--full-bleed {
  padding: 0 !important;
  background: transparent !important;
  min-height: calc(100vh - 60px);
}
</style>
