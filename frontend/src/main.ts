import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'

import App from './App.vue'
import Home from './views/Home.vue'
import Result from './views/Result.vue'

// 创建前端路由实例。
// createWebHistory 使用浏览器原生 history 模式，URL 更干净，适合现代单页应用。
const router = createRouter({
  history: createWebHistory(),

  // 定义页面路径与组件之间的映射关系。
  // 用户访问不同 URL 时，router-view 会渲染对应的页面组件。
  routes: [
    {
      // 首页：通常用于收集用户的旅行需求，例如目的地、时间、预算等。
      path: '/',
      name: 'Home',
      component: Home
    },
    {
      // 结果页：通常用于展示后端或智能体生成的旅行规划结果。
      path: '/result',
      name: 'Result',
      component: Result
    }
  ]
})

// 以 App.vue 作为根组件创建 Vue 应用实例。
// App.vue 决定整个应用的外层布局，具体页面内容由路由动态切换。
const app = createApp(App)

// 注册路由插件，使整个应用都可以使用 <router-view>、页面跳转等能力。
app.use(router)

// 注册 Ant Design Vue 组件库，使页面可以直接使用 a-layout、a-button 等组件。
app.use(Antd)

// 将 Vue 应用挂载到 index.html 中 id 为 app 的 DOM 节点上。
app.mount('#app')