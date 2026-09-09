/**
 * 匿名面试访问凭证保存在当前浏览器会话中。
 * 分享/演示链接可把凭证放在 URL fragment，读取后立即从地址栏清除，避免发给服务器。
 */
export function storeInterviewToken(interviewId, token) {
  if (token) sessionStorage.setItem(`interview-token:${interviewId}`, token)
}

export function getInterviewToken(interviewId) {
  const params = new URLSearchParams(location.hash.replace(/^#/, ''))
  const fragmentToken = params.get('access_token') || ''
  if (fragmentToken) {
    storeInterviewToken(interviewId, fragmentToken)
    history.replaceState(null, '', `${location.pathname}${location.search}`)
  }
  return fragmentToken || sessionStorage.getItem(`interview-token:${interviewId}`) || ''
}

/**
 * 本会话上传过的简历凭据,供「简历评审」独立页复用。
 */
export function storeCandidate(cand) {
  if (cand?.id && cand?.access_token) {
    sessionStorage.setItem(
      'candidate-session',
      JSON.stringify({
        id: cand.id,
        accessToken: cand.access_token,
        name: cand.name || '',
      })
    )
  }
}

export function getCandidate() {
  try {
    const raw = sessionStorage.getItem('candidate-session')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * 交流区匿名身份:浏览器本地随机生成令牌(服务端只存哈希),
 * 昵称由服务端按哈希派生;同一会话内发言/点赞身份稳定。
 */
export function getCommunityToken() {
  let token = sessionStorage.getItem('community-token')
  if (!token) {
    const bytes = new Uint8Array(24)
    crypto.getRandomValues(bytes)
    token = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
    sessionStorage.setItem('community-token', token)
  }
  return token
}
