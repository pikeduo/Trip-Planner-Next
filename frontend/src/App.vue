<template>
  <div id="app">
    <!--
      应用最外层布局。
      min-height: 100vh 保证页面高度至少占满整个浏览器窗口，
      避免内容较少时底部区域悬在页面中间。
    -->
    <a-layout style="min-height: 100vh">
      <!-- 顶部导航栏：展示项目名称，帮助用户明确当前应用身份。 -->
      <a-layout-header style="background: #001529; padding: 0 50px">
        <div style="color: white; font-size: 24px; font-weight: bold">
          🌍 Trip Planner Next 智能旅行助手
        </div>
      </a-layout-header>

      <!--
        页面主体区域。
        router-view 是 Vue Router 的占位组件：
        当前 URL 匹配到哪个页面组件，这里就渲染哪个组件。
      -->
      <a-layout-content style="padding: 24px">
        <router-view />
      </a-layout-content>

      <!-- 页面底部：展示项目版权和技术栈说明。 -->
      <a-layout-footer style="text-align: center">
        Trip Planner Next ©2026 基于 LangGraph + MCP
      </a-layout-footer>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
/*
  当前根组件没有本地状态、计算属性或生命周期逻辑，
  主要职责是提供全局布局容器。
*/
</script>

<style>
/*
  设置全局字体栈。
  优先使用系统字体，可以让应用在 macOS、Windows、Linux 等平台上
  都保持较自然的显示效果。
*/
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans', sans-serif;
}
</style>