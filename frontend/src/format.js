/** 交流区时间显示:刚刚 / N 分钟前 / N 小时前 / N 天前 / YYYY-MM-DD。 */
export function timeAgo(value) {
  const t = new Date(value).getTime()
  if (Number.isNaN(t)) return ''
  const diff = Date.now() - t
  const min = Math.floor(diff / 60_000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour} 小时前`
  const day = Math.floor(hour / 24)
  if (day < 30) return `${day} 天前`
  return new Date(t).toISOString().slice(0, 10)
}
