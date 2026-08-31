<template>
  <div class="hall">
    <header class="topbar">
      <div class="brand">
        <span class="brand-dot">🎙</span>
        <div class="brand-text">
          <span class="brand-name">面评家</span>
          <span class="brand-sub">AI 模拟面试官 · 个人竞争力报告</span>
        </div>
      </div>
      <nav class="nav">
        <router-link class="nav-link" to="/jobs/submit">发布招聘信息</router-link>
        <router-link class="nav-link ghost" to="/review">官方审核</router-link>
      </nav>
    </header>

    <section class="hero">
      <h1>选一个岗位,先让 AI 面试官面你一次</h1>
      <p>上传简历 → 查看人岗匹配分析 → 与数字人面试官模拟对话 → 拿到你的专属竞争力报告</p>
    </section>

    <main class="body">
      <p v-if="state.loading" class="tip">加载岗位中…</p>
      <p v-else-if="state.error" class="tip err">{{ state.error }}</p>
      <div v-else-if="!state.jobs.length" class="tip">
        暂无已上架岗位,<router-link to="/jobs/submit">去发布一个</router-link>
      </div>
      <div v-else class="grid">
        <article v-for="j in state.jobs" :key="j.id" class="card">
          <div class="card-head">
            <h2 class="title">{{ j.title }}</h2>
            <span class="company">{{ j.company || '面评家官方岗位' }}</span>
          </div>
          <p class="jd">{{ (j.jd_text || '').slice(0, 90) }}…</p>
          <div class="dims" v-if="dimNames(j).length">
            <span class="chip" v-for="d in dimNames(j)" :key="d">{{ d }}</span>
          </div>
          <div class="card-foot">
            <span class="dim-count" v-if="j.dimensions">
              {{ j.dimensions.length }} 个考察维度
            </span>
            <span class="dim-count warn" v-else>岗位分析中…</span>
            <router-link
              class="go"
              :to="`/apply/${j.id}`"
              :class="{ disabled: !j.dimensions }"
              @click.prevent="go(j)"
            >开始面试 →</router-link>
          </div>
        </article>
      </div>
    </main>
  </div>
</template>

<script>
import { onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { jobs } from '../api'

export default {
  name: 'JobHallView',
  setup() {
    const router = useRouter()
    const state = reactive({ jobs: [], loading: true, error: '' })

    const dimNames = (j) => (j.dimensions || []).slice(0, 4).map((d) => d.name)

    function go(j) {
      if (!j.dimensions || !j.dimensions.length) return
      router.push(`/apply/${j.id}`)
    }

    onMounted(async () => {
      try {
        state.jobs = await jobs.list('approved')
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    })

    return { state, dimNames, go }
  },
}
</script>

<style scoped>
.hall {
  min-height: 100vh;
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 20px 40px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 16px 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-dot {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  box-shadow: 0 4px 10px rgba(26, 115, 232, 0.3);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.brand-name {
  font-weight: 700;
  font-size: 18px;
  color: #1a3a63;
}

.brand-sub {
  font-size: 11px;
  color: #8a97a8;
}

.nav {
  display: flex;
  gap: 10px;
}

.nav-link {
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
  border: 1px solid #1a73e8;
  padding: 6px 14px;
  border-radius: 999px;
}

.nav-link.ghost {
  color: #5f6b7a;
  border-color: #dde3ec;
}

.nav-link:hover {
  background: #e8f1fd;
}

.hero {
  text-align: center;
  padding: 40px 16px 30px;
}

.hero h1 {
  font-size: clamp(21px, 4.6vw, 28px);
  color: #1a3a63;
  margin-bottom: 12px;
}

.hero p {
  font-size: 14px;
  color: #6b7a8d;
}

.grid {
  display: grid;
  /* min(300px,100%) 防止窄屏下 minmax 下限撑破容器 */
  grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
  gap: 16px;
}

.card {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(30, 60, 110, 0.1);
}

.card-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title {
  font-size: 16px;
  color: #2c3e50;
}

.company {
  font-size: 12px;
  color: #8a97a8;
}

.jd {
  font-size: 13px;
  color: #5f6b7a;
  line-height: 1.6;
  flex: 1;
}

.dims {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  font-size: 11px;
  color: #1a73e8;
  background: #e8f1fd;
  padding: 3px 9px;
  border-radius: 999px;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #eef1f5;
  padding-top: 10px;
}

.dim-count {
  font-size: 12px;
  color: #9aa5b1;
}

.dim-count.warn {
  color: #b26a00;
}

.go {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  text-decoration: none;
  padding: 7px 16px;
  border-radius: 999px;
  box-shadow: 0 3px 8px rgba(26, 115, 232, 0.3);
}

.go.disabled {
  background: #c6d4e8;
  box-shadow: none;
  pointer-events: none;
}

.tip {
  text-align: center;
  color: #9aa5b1;
  padding: 60px 0;
  font-size: 14px;
}

.tip.err {
  color: #e5533d;
}

.tip a {
  color: #1a73e8;
}

@media (max-width: 640px) {
  .hall {
    padding: 0 12px 32px;
  }

  .topbar {
    flex-wrap: wrap;
    gap: 10px;
  }

  .hero {
    padding: 26px 2px 20px;
  }

  .hero h1 {
    font-size: 22px;
  }

  .hero p {
    font-size: 12.5px;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
