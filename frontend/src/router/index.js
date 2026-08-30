import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/admin' },
  // 候选人免登录面试页:链接 = http://host/interview/{id}
  {
    path: '/interview/:id',
    name: 'interview',
    component: () => import('../candidate/InterviewView.vue'),
  },
  // HR 后台(建设中)
  { path: '/admin', name: 'admin', component: () => import('../admin/DashboardView.vue') },
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
