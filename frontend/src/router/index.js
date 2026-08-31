import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/admin' },
  // 应聘者免登录面试页:链接 = http://host/interview/{id}
  {
    path: '/interview/:id',
    name: 'interview',
    component: () => import('../candidate/InterviewView.vue'),
  },
  // 演示后台(岗位库/简历库/面试库,内部工具)
  { path: '/admin', name: 'admin', component: () => import('../admin/DashboardView.vue') },
  { path: '/admin/comparison', name: 'comparison', component: () => import('../admin/ComparisonView.vue') },
  {
    path: '/admin/interview/:id',
    name: 'report',
    component: () => import('../admin/ReportView.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
