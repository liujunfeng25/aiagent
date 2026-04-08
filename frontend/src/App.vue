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
  /* Token：与登录/command 台色相连续；登录页全屏背景会盖住 */
  background: var(--sx-app-gradient);
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
  opacity: var(--sx-tech-bg-opacity);
  mix-blend-mode: screen;
}
.layout > .el-container,
.layout > .el-aside {
  position: relative;
  z-index: 1;
}
.sidebar {
  background: var(--sx-sidebar-bg);
  border-right: 1px solid var(--sx-sidebar-border);
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
  background: var(--sx-logo-dot);
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
  color: var(--sx-text-muted);
}
.el-menu { border: none; background: transparent; }
.menu-group {
  color: var(--sx-text-readable-dim);
  font-size: 12px;
  letter-spacing: 0.08em;
  font-weight: 600;
}
.el-sub-menu :deep(.el-sub-menu__title) {
  color: var(--sx-text-readable-muted);
  background: rgba(255, 255, 255, 0.03);
  font-weight: 500;
}
.el-menu-item {
  color: var(--sx-text-body);
  margin: 2px 8px;
  border-radius: 8px;
  font-weight: 500;
}
.el-menu-item:hover, .el-menu-item.is-active {
  color: #fff;
  background: var(--sx-menu-hover);
}
.header {
  background: var(--sx-header-bg);
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
  position: relative;
  isolation: isolate;
  /* 先铺 scrim 再叠微弱氛围色，保证全站主区文字不被粒子/网格「穿透」糊住 */
  background:
    var(--sx-main-scrim),
    radial-gradient(ellipse 100% 70% at 50% 0%, var(--sx-main-radial), transparent 55%),
    var(--sx-main-gradient);
  padding: 24px;
  min-height: calc(100vh - 60px);
  /* 主区内 Element Plus 默认浅色填充改为深色玻璃气质（模型库等列表页） */
  --el-card-bg-color: var(--sx-content-card-bg);
  --el-card-border-color: var(--sx-glass-border);
  --el-text-color-primary: var(--sx-text-title);
  --el-text-color-regular: var(--sx-text-body);
  --el-text-color-secondary: var(--sx-text-readable-muted);
  --el-text-color-placeholder: var(--sx-text-dim);
  --el-border-color: var(--sx-glass-border);
  --el-border-color-light: var(--sx-edge-cyan-mid);
  --el-border-color-lighter: rgba(34, 211, 238, 0.12);
  --el-fill-color-blank: rgba(15, 23, 42, 0.52);
  --el-fill-color-light: rgba(30, 144, 255, 0.14);
  --el-fill-color-lighter: rgba(30, 58, 90, 0.32);
  --el-table-bg-color: rgba(15, 23, 42, 0.42);
  --el-table-tr-bg-color: rgba(15, 23, 42, 0.42);
  --el-table-header-bg-color: rgba(8, 22, 48, 0.94);
  --el-table-header-text-color: var(--sx-text-table-header);
  --el-table-text-color: var(--sx-text-table-cell);
  --el-table-border-color: var(--sx-edge-cyan-mid);
  --el-table-row-hover-bg-color: rgba(30, 144, 255, 0.14);
  --el-color-primary-light-9: rgba(30, 144, 255, 0.14);
  /* 说明条、表单与 Tab：避免 EP 默认大白底块 */
  --el-alert-padding: 12px 16px;
}

.main .el-form-item__label {
  color: var(--sx-text-readable-muted) !important;
  font-weight: 500;
}

.main .el-tabs__item {
  color: var(--sx-text-readable-dim);
  font-weight: 500;
}
.main .el-tabs__item.is-active {
  color: var(--sx-cyan-light);
}
.main .el-tabs__active-bar {
  background-color: var(--sx-primary);
}
.main .el-tabs__nav-wrap::after {
  background-color: var(--sx-edge-cyan-mid);
}

/* Alert：深色玻璃，替代 is-light 大白底 */
.main .el-alert.is-light {
  border: 1px solid var(--sx-glass-border);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.main .el-alert.el-alert--info.is-light {
  background: rgba(10, 20, 44, 0.92) !important;
}
.main .el-alert.is-light .el-alert__title {
  color: var(--sx-text-bright);
  font-weight: 600;
}
.main .el-alert.is-light .el-alert__description {
  color: var(--sx-text-readable-muted);
  line-height: 1.55;
}
.main .el-alert.is-light .el-alert__icon {
  color: var(--sx-cyan-light);
}
.main .el-alert--warning.is-light {
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(45, 32, 12, 0.88) !important;
}
.main .el-alert--warning.is-light .el-alert__icon {
  color: var(--sx-warning);
}
.main .el-alert--error.is-light {
  border-color: rgba(248, 113, 113, 0.5);
  background: rgba(50, 22, 24, 0.9) !important;
}
.main .el-alert--error.is-light .el-alert__icon {
  color: #fca5a5;
}
.main .el-alert--success.is-light {
  border-color: rgba(52, 211, 153, 0.4);
  background: rgba(12, 38, 32, 0.88) !important;
}
.main .el-alert--success.is-light .el-alert__icon {
  color: var(--sx-success);
}

.main .el-button--danger {
  --el-button-bg-color: rgba(220, 38, 38, 0.92);
  --el-button-border-color: rgba(252, 165, 165, 0.45);
  --el-button-hover-bg-color: rgba(239, 68, 68, 0.98);
  --el-button-hover-border-color: rgba(254, 202, 202, 0.55);
  --el-button-text-color: #fff;
}
.main .el-button--danger.is-plain {
  --el-button-bg-color: rgba(127, 29, 29, 0.35);
  --el-button-border-color: rgba(248, 113, 113, 0.55);
  --el-button-text-color: #fecaca;
  --el-button-hover-bg-color: rgba(185, 28, 28, 0.45);
  --el-button-hover-text-color: #fff;
}

.main .el-divider__text {
  background: transparent;
  color: var(--sx-text-readable-muted);
  font-weight: 500;
}
.main .el-divider--horizontal {
  border-top-color: var(--sx-edge-cyan-mid);
}

.main .el-card {
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: var(--sx-panel-shadow);
  border-radius: var(--sx-radius-panel);
}

.main .el-card .el-card__header {
  border-bottom-color: var(--sx-edge-cyan-mid);
  color: var(--sx-text-title);
}

.main .el-table .cell {
  color: var(--sx-text-table-cell);
  font-variant-numeric: tabular-nums;
}

.main .el-table .cell .cell-datetime {
  color: var(--sx-text-datetime);
  font-weight: 500;
  letter-spacing: 0.02em;
}

.main--full-bleed {
  padding: 0 !important;
  background: transparent !important;
  min-height: calc(100vh - 60px);
}
</style>
