<template>
  <el-config-provider :locale="zhCn">
    <el-container class="layout">
      <el-aside width="220px" class="sidebar">
        <div class="logo">AI Agent</div>
        <el-menu :default-active="$route.path" router>
          <el-menu-item index="/">
            <el-icon><Odometer /></el-icon>
            <span>工作台</span>
          </el-menu-item>
          <el-menu-item index="/datasources">
            <el-icon><Connection /></el-icon>
            <span>数据源</span>
          </el-menu-item>
          <el-menu-item index="/datasets">
            <el-icon><Folder /></el-icon>
            <span>数据集</span>
          </el-menu-item>
          <el-menu-item index="/categories">
            <el-icon><Collection /></el-icon>
            <span>类别管理</span>
          </el-menu-item>
          <el-menu-item index="/training">
            <el-icon><VideoPlay /></el-icon>
            <span>训练管理</span>
          </el-menu-item>
          <el-menu-item index="/models">
            <el-icon><Box /></el-icon>
            <span>模型库</span>
          </el-menu-item>
          <el-menu-item index="/recognition">
            <el-icon><PictureFilled /></el-icon>
            <span>识别中心</span>
          </el-menu-item>
          <el-menu-item index="/analysis">
            <el-icon><DataAnalysis /></el-icon>
            <span>分析中心</span>
          </el-menu-item>
          <el-menu-item index="/price">
            <el-icon><TrendCharts /></el-icon>
            <span>报价抓取</span>
          </el-menu-item>
          <el-menu-item index="/system">
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-container>
        <el-header class="header">
          <span class="title">AI 训练与数据智能平台</span>
        </el-header>
        <el-main class="main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </el-config-provider>
</template>

<script setup>
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { Odometer, Connection, Folder, Collection, VideoPlay, Box, PictureFilled, DataAnalysis, TrendCharts, Setting } from '@element-plus/icons-vue'
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; }
.layout { height: 100%; }
.sidebar { background: #001529; }
.logo { padding: 16px; color: #fff; font-size: 18px; font-weight: bold; }
.el-menu { border: none; background: transparent; }
.el-menu-item { color: rgba(255,255,255,0.85); }
.el-menu-item:hover, .el-menu-item.is-active { color: #fff; background: rgba(255,255,255,0.1); }
.header { background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.1); display: flex; align-items: center; padding: 0 24px; }
.title { font-size: 16px; font-weight: 500; }
.main { background: #f0f2f5; padding: 24px; min-height: calc(100vh - 60px); }
</style>
