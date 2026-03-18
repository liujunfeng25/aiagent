<template>
  <div class="price-page">
    <h2 class="page-title">报价抓取</h2>
    <el-card class="iframe-card">
      <iframe
        src="/admin/price"
        title="新发地价格行情"
        class="price-iframe"
      />
    </el-card>
  </div>
</template>

<script setup>
</script>

<style scoped>
.page-title { margin-bottom: 16px; font-size: 20px; }
.iframe-card { padding: 0; overflow: hidden; }
.price-iframe {
  display: block;
  width: 100%;
  min-height: calc(100vh - 180px);
  border: none;
}
</style>
