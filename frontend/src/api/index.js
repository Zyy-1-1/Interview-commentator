// 后端 API 封装(vite dev server 已将 /api 代理到 FastAPI)
const BASE = '/api'
const API_TIMEOUT_MS = 90_000

function adminHeaders(passphrase) {
  return passphrase ? { 'X-Review-Passphrase': passphrase } : {}
}

function candidateHeaders(token) {
  return token ? { 'X-Candidate-Token': token } : {}
}

function communityHeaders(token) {
  return token ? { 'X-Community-Token': token } : {}
}

async function request(path, options = {}) {
  let resp
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS)
  const headers = new Headers(options.headers || {})
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  try {
    resp = await fetch(`${BASE}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    })
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('请求超时,请稍后重试')
    }
    throw new Error('网络异常，请确认服务连接后重试')
  } finally {
    window.clearTimeout(timer)
  }
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    const error = new Error(typeof data.detail === 'string' ? data.detail : `请求失败(${resp.status})`)
    error.status = resp.status
    throw error
  }
  return data
}

export const jobs = {
  // 大厅默认只看已上架;审核页传 status=pending / all
  list: (status = 'approved', passphrase = '') =>
    request(`/jobs?status=${encodeURIComponent(status)}`, {
      headers: adminHeaders(passphrase),
    }),
  // 任务4:带分类筛选的岗位查询(filters 为 {category,education,recruit_type,major,salary_min,salary_max,q})
  search: (filters = {}) => {
    const params = new URLSearchParams({ status: 'approved' })
    for (const [k, v] of Object.entries(filters)) {
      if (v !== '' && v != null) params.set(k, v)
    }
    return request(`/jobs?${params.toString()}`)
  },
  // 筛选项可选值(类别/学历/招聘类型/薪资范围)
  facets: () => request('/jobs/facets'),
  get: (id) => request(`/jobs/${id}`),
  create: (title, jdText, company) =>
    request('/jobs', {
      method: 'POST',
      body: JSON.stringify({
        title,
        jd_text: jdText,
        company: company || null,
      }),
    }),
  auth: (passphrase) =>
    request('/jobs/review/auth', {
      method: 'POST',
      headers: adminHeaders(passphrase),
    }),
  review: (passphrase, jobId, approve, note = null) =>
    request('/jobs/review', {
      method: 'POST',
      headers: adminHeaders(passphrase),
      body: JSON.stringify({
        job_id: jobId,
        approve,
        note,
      }),
    }),
}

export const candidates = {
  list: (passphrase) => request('/candidates', { headers: adminHeaders(passphrase) }),
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/candidates', { method: 'POST', body: form })
  },
  // 面试前的人岗匹配分析
  match: (candidateId, jobId, token) =>
    request(`/candidates/${candidateId}/match/${jobId}`, {
      headers: candidateHeaders(token),
    }),
}

export const interviews = {
  list: (passphrase) => request('/interviews', { headers: adminHeaders(passphrase) }),
  get: (id, token) =>
    request(`/interviews/${id}`, { headers: candidateHeaders(token) }),
  create: (jobId, candidateId, style = 'pro', token) =>
    request('/interviews', {
      method: 'POST',
      headers: candidateHeaders(token),
      body: JSON.stringify({
        job_id: jobId,
        candidate_id: candidateId,
        style,
      }),
    }),
  // 面试状态(进度)
  state: (id, token) =>
    request(`/interviews/${id}/state`, { headers: candidateHeaders(token) }),
  // 历史消息
  messages: (id, token) =>
    request(`/interviews/${id}/messages`, { headers: candidateHeaders(token) }),
  // 提交回答(reply 传 null/undefined 触发开场白)
  message: (id, reply, requestId, token) =>
    request(`/interviews/${id}/message`, {
      method: 'POST',
      headers: candidateHeaders(token),
      body: JSON.stringify({ reply: reply ?? null, request_id: requestId }),
    }),
  // 多应聘者横向对比(演示用,按岗位分组)
  comparison: (passphrase) =>
    request('/interviews/comparison', { headers: adminHeaders(passphrase) }),
  // 评估报告
  report: (id, token) =>
    request(`/interviews/${id}/report`, { headers: candidateHeaders(token) }),
  evaluate: (id, token) =>
    request(`/interviews/${id}/evaluate`, {
      method: 'POST',
      headers: candidateHeaders(token),
    }),
}

export const community = {
  me: (token) => request('/community/me', { headers: communityHeaders(token) }),
  list: (token) => request('/community/posts', { headers: communityHeaders(token) }),
  create: (token, title, content) =>
    request('/community/posts', {
      method: 'POST',
      headers: communityHeaders(token),
      body: JSON.stringify({ title, content }),
    }),
  get: (id, token) =>
    request(`/community/posts/${id}`, { headers: communityHeaders(token) }),
  comment: (id, token, content) =>
    request(`/community/posts/${id}/comments`, {
      method: 'POST',
      headers: communityHeaders(token),
      body: JSON.stringify({ content }),
    }),
  like: (id, token) =>
    request(`/community/posts/${id}/like`, {
      method: 'POST',
      headers: communityHeaders(token),
    }),
}
