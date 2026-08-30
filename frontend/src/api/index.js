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

export const interviews = {
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
  // 评估报告
  report: (id) => request(`/interviews/${id}/report`),
  evaluate: (id) =>
    request(`/interviews/${id}/evaluate`, { method: 'POST' }),
}
