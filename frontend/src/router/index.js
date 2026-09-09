import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // 首页 = 岗位大厅(应聘者入口)
  { path: '/', name: 'hall', component: () => import('../views/JobHallView.vue') },
  // 简历分析页:上传 → 选风格 → 直接开始面试
  {
    path: '/apply/:jobId',
    name: 'apply',
    component: () => import('../views/ResumeAnalysisView.vue'),
  },
  // 简历评审独立页:人岗匹配分析评审单
  {
    path: '/match',
    name: 'match',
    component: () => import('../views/MatchReportView.vue'),
  },
  // 应聘者免登录面试页(数字人 + 语音):/interview/{id}
  {
    path: '/interview/:id',
    name: 'interview',
    component: () => import('../candidate/InterviewView.vue'),
  },
  // 岗位自助提交(任何人可提交,待官方审核)
  { path: '/jobs/submit', name: 'submit', component: () => import('../views/JobSubmitView.vue') },
  // 交流区(牛客式板块:发帖 / 评论 / 点赞,匿名)
  { path: '/community', name: 'community', component: () => import('../views/CommunityView.vue') },
  {
    path: '/community/:id',
    name: 'community-post',
    component: () => import('../views/PostDetailView.vue'),
  },
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
