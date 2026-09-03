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
