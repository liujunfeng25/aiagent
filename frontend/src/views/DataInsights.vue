<template>
  <div class="data-insights">
    <header class="insight-page-head">
      <h1>数据洞察</h1>
      <p class="sub">多源数据一览 · 辅助经营决策</p>
    </header>

    <el-tabs v-model="activeTab" class="insight-tabs" @tab-change="onTabChange">
      <el-tab-pane label="订单与销售" name="orders">
        <BusinessOrders />
      </el-tab-pane>
      <el-tab-pane label="新发地批发价" name="xinfadi" lazy>
        <XinfadiTrends />
      </el-tab-pane>
      <el-tab-pane label="缺货与背单" name="backorder" lazy>
        <BusinessBackorder />
      </el-tab-pane>
      <el-tab-pane label="库内价格汇总" name="xfdb" lazy>
        <BusinessXinfadiDb />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import XinfadiTrends from './insights/XinfadiTrends.vue'
import BusinessOrders from './insights/BusinessOrders.vue'
import BusinessBackorder from './insights/BusinessBackorder.vue'
import BusinessXinfadiDb from './insights/BusinessXinfadiDb.vue'

const route = useRoute()
const router = useRouter()

const TAB_NAMES = new Set(['orders', 'xinfadi', 'backorder', 'xfdb'])

const activeTab = ref('orders')

function syncTabFromRoute() {
  const t = route.query.tab
  if (TAB_NAMES.has(t)) activeTab.value = t
  else if (t === 'more' || t === 'sql') activeTab.value = 'orders'
  else activeTab.value = 'orders'
}

/** Element Plus 下划线在首屏/路由同步后偶发偏移，触发 resize 让导航条重算 */
function fixTabsInkBar() {
  nextTick(() => {
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'))
    })
  })
}

function onTabChange(name) {
  const q = { ...route.query }
  if (name === 'orders') delete q.tab
  else q.tab = name
  router.replace({ path: '/insights', query: q })
  fixTabsInkBar()
  setTimeout(fixTabsInkBar, 80)
}

onMounted(() => {
  syncTabFromRoute()
  fixTabsInkBar()
  setTimeout(fixTabsInkBar, 120)
})
watch(() => route.query.tab, () => {
  syncTabFromRoute()
  fixTabsInkBar()
})
</script>

<style scoped>
.data-insights {
  max-width: 1280px;
  margin: 0 auto;
}

.insight-page-head {
  margin-bottom: 20px;
}
.insight-page-head h1 {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.insight-page-head .sub {
  margin-top: 6px;
  font-size: 14px;
  color: #64748b;
}

.insight-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}
.insight-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
}
.insight-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: #e2e8f0;
}
</style>
