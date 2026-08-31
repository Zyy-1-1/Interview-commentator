import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // 首页 = 岗位大厅(应聘者入口)
  { path: '/', name: 'hall', component: () => import('../views/JobHallView.vue') },
  // 简历分析独立页:上传 → 人岗匹配 → 决定是否开始面试
  {
    path: '/apply/:jobId',
    name: 'apply',
    component: () => import('../views/ResumeAnalysisView.vue'),
  },
  // 应聘者免登录面试页(数字人 + 语音):/interview/{id}
  {
    path: '/interview/:id',
    name: 'interview',
    component: () => import('../candidate/InterviewView.vue'),
  },
  // 岗位自助提交(任何人可提交,待官方审核)
  { path: '/jobs/submit', name: 'submit', component: () => import('../views/JobSubmitView.vue') },
  // 官方审核页(口令门控)
  { path: '/review', name: 'review', component: () => import('../views/ReviewView.vue') },
  // 个人竞争力报告
  {
    path: '/admin/reports/:id',
    name: 'report',
    component: () => import('../admin/ReportView.vue'),
  },
  // 旧后台路由已删除,统一回大厅
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
