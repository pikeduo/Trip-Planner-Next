import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import Home from './views/Home.vue'
import Result from './views/Result.vue'

// 创建前端路由实例。
// createWebHistory 使用浏览器原生 history 模式，让页面 URL 保持为 /result 这类更自然的路径。
const router = createRouter({
  history: createWebHistory(),
  // 定义页面路径与组件之间的映射关系。
  // 当用户访问不同 URL 时，根组件中的路由占位区域会渲染对应页面组件。
  routes: [
    {
      // 首页通常承载旅行需求输入，例如目的地、日期、预算等信息。
      path: '/',
      name: 'Home',
      component: Home
    },
    {
      // 结果页通常承载智能旅行规划的生成结果展示。
      path: '/result',
      name: 'Result',
      component: Result
    }
  ]
})

// 以 App.vue 作为根组件创建 Vue 应用实例。
// App.vue 负责整体布局，具体业务页面由路由动态切换。
const app = createApp(App)

// 注册路由插件，使应用可以使用页面跳转和路由页面渲染能力。
app.use(router)

// 注册 Ant Design Vue 组件库，使页面可以直接使用 a-layout、a-button 等组件。
app.use(Antd)

// 将 Vue 应用挂载到 index.html 中 id 为 app 的 DOM 节点上。
app.mount('#app')
