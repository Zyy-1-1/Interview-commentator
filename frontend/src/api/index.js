// 后端 API 封装(vite dev server 已将 /api 代理到 FastAPI)
const BASE = '/api'

async function request(path, options = {}) {
  let resp
  try {
    resp = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new Error('网络异常,请确认后端服务已启动(localhost:8000)')
  }
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    throw new Error(data.detail || `请求失败(${resp.status})`)
  }
  return data
}

export const jobs = {
  // 大厅默认只看已上架;审核页传 status=pending / all
  list: (status = 'approved') => request(`/jobs?status=${encodeURIComponent(status)}`),
  get: (id) => request(`/jobs/${id}`),
  create: (title, jdText, company, skipReview = false) =>
    request('/jobs', {
      method: 'POST',
      body: JSON.stringify({
        title,
        jd_text: jdText,
        company: company || null,
        skip_review: skipReview,
      }),
    }),
  review: (passphrase, jobId, approve, note = null) =>
    request('/jobs/review', {
      method: 'POST',
      body: JSON.stringify({
        passphrase,
        job_id: jobId,
        approve,
        note,
      }),
    }),
}

export const candidates = {
  list: () => request('/candidates'),
  upload: async (file) => {
    const form = new FormData()
    form.append('file', file)
    let resp
    try {
      resp = await fetch(`${BASE}/candidates`, { method: 'POST', body: form })
    } catch {
      throw new Error('网络异常,请确认后端服务已启动')
    }
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.detail || `上传失败(${resp.status})`)
    return data
  },
  // 面试前的人岗匹配分析
  match: (candidateId, jobId) =>
    request(`/candidates/${candidateId}/match/${jobId}`),
}

export const interviews = {
  list: () => request('/interviews'),
  get: (id) => request(`/interviews/${id}`),
  create: (jobId, candidateId, style = 'pro') =>
    request('/interviews', {
      method: 'POST',
      body: JSON.stringify({
        job_id: jobId,
        candidate_id: candidateId,
        style,
      }),
    }),
  // 面试状态(进度)
  state: (id) => request(`/interviews/${id}/state`),
  // 历史消息
  messages: (id) => request(`/interviews/${id}/messages`),
  // 提交回答(reply 传 null/undefined 触发开场白)
  message: (id, reply) =>
    request(`/interviews/${id}/message`, {
      method: 'POST',
      body: JSON.stringify({ reply: reply ?? null }),
    }),
  // 多应聘者横向对比(演示用,按岗位分组)
  comparison: () => request('/interviews/comparison'),
  // 评估报告
  report: (id) => request(`/interviews/${id}/report`),
  evaluate: (id) =>
    request(`/interviews/${id}/evaluate`, { method: 'POST' }),
}
