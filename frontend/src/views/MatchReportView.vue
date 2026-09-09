<template>
  <div class="match-page">
    <header class="topbar">
      <router-link class="back" to="/">← 返回岗位大厅</router-link>
      <h1 class="page-title">简历评审 · 人岗匹配分析</h1>
    </header>

    <!-- 简历来源:本会话已上传 或 现场上传 -->
    <section class="panel">
      <h2>评审简历</h2>
      <template v-if="cand">
        <p class="cand-line">
          本次使用:<b>{{ cand.name || '(未识别姓名)' }}</b>
          <button class="ghost" @click="clearCand">移除</button>
        </p>
      </template>
      <template v-else>
        <div class="upload-zone" :class="{ hover: dragHover }"
          @dragover.prevent="dragHover = true" @dragleave="dragHover = false"
          @drop.prevent="onDrop">
          <p class="sub">拖拽或选择简历文件(PDF / DOCX / Markdown / TXT)</p>
          <button class="ghost" :disabled="uploading" @click="$refs.file.click()">
            {{ uploading ? '解析中…' : '上传简历' }}
          </button>
          <input ref="file" type="file" accept=".pdf,.docx,.txt,.md" hidden @change="onFile" />
        </div>
      </template>
    </section>

    <!-- 岗位选择 -->
    <section class="panel">
      <h2>目标岗位</h2>
      <p v-if="loadingJobs" class="sub">加载岗位中…</p>
      <select v-else v-model="jobId" class="job-select">
        <option :value="0" disabled>请选择岗位</option>
        <option v-for="j in jobList" :key="j.id" :value="j.id">
          {{ j.title }}@{{ j.company || '面评家官方岗位' }}
        </option>
      </select>
      <button class="primary" :disabled="!canGenerate || loading" @click="generate">
        {{ loading ? 'AI 逐维度比对中…' : '生成评审单' }}
      </button>
      <p v-if="loading" class="dots-line">
        正在比对简历与岗位要求 <span class="dots"><i></i><i></i><i></i></span>
      </p>
      <p v-if="error" class="err">{{ error }}</p>
    </section>

    <!-- 评审单 -->
    <section class="panel" v-if="match">
      <h2>评审单 · {{ jobTitle }}</h2>
      <div class="score-row">
        <div class="big-score" :class="scoreClass">{{ match.overall }}</div>
        <div class="score-cap">
          <b>整体匹配度</b>
          <p>{{ match.summary }}</p>
        </div>
      </div>
      <div ref="chartEl" class="chart"></div>
      <div class="hl-gap">
        <div class="hl">
          <h3>✦ 亮点</h3>
          <ul><li v-for="(h, i) in match.highlights" :key="i">{{ h }}</li></ul>
        </div>
        <div class="gap">
          <h3>⚠ 短板</h3>
          <ul><li v-for="(g, i) in match.gaps" :key="i">{{ g }}</li></ul>
        </div>
      </div>
      <router-link
        v-if="jobId"
        class="to-interview"
        :to="`/apply/${jobId}`"
      >按这份简历直接去模拟面试 →</router-link>
    </section>
  </div>
</template>

<script>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { candidates, jobs } from '../api'
import { getCandidate, storeCandidate } from '../access'
import { init as initChart } from '../lib/echarts'

export default {
  name: 'MatchReportView',
  setup() {
    const route = useRoute()
    const chartEl = ref(null)
    let chart = null
    let disposed = false

    const cand = ref(getCandidate())
    const jobList = ref([])
    const jobId = ref(Number(route.query.job) || 0)
    const loadingJobs = ref(true)
    const loading = ref(false)
    const uploading = ref(false)
    const dragHover = ref(false)
    const error = ref('')
    const match = ref(null)
    const state = reactive({})

    const jobTitle = computed(
      () => jobList.value.find((j) => j.id === jobId.value)?.title || ''
    )

    const canGenerate = computed(() => !!cand.value && jobId.value > 0)

    const scoreClass = computed(() => {
      const v = match.value?.overall || 0
      return v >= 75 ? 'high' : v >= 55 ? 'mid' : 'low'
    })

    function renderChart() {
      const el = chartEl.value
      const dims = match.value?.dimension_scores || []
      if (!el || !dims.length) return
      if (!chart) chart = initChart(el)
      chart.setOption({
        radar: {
          indicator: dims.map((d) => ({ name: d.name, max: 10 })),
          radius: '62%',
        },
        tooltip: {},
        series: [
          {
            type: 'radar',
            data: [
              {
                value: dims.map((d) => d.score),
                name: '简历匹配度',
                areaStyle: { opacity: 0.25 },
                lineStyle: { color: '#1a73e8' },
                itemStyle: { color: '#1a73e8' },
              },
            ],
          },
        ],
      })
    }

    function disposeChart() {
      chart?.dispose()
      chart = null
    }

    async function generate() {
      if (!canGenerate.value || loading.value) return
      loading.value = true
      error.value = ''
      disposeChart()
      match.value = null
      try {
        const result = await candidates.match(cand.value.id, jobId.value, cand.value.accessToken)
        if (disposed) return
        match.value = result
        await nextTick()
        if (!disposed) renderChart()
      } catch (e) {
        if (!disposed) error.value = e.message
      } finally {
        if (!disposed) loading.value = false
      }
    }

    async function handleFile(file) {
      if (!file || uploading.value) return
      uploading.value = true
      error.value = ''
      try {
        const created = await candidates.upload(file)
        storeCandidate(created)
        cand.value = {
          id: created.id,
          accessToken: created.access_token,
          name: created.name || '',
        }
      } catch (e) {
        error.value = e.message
      } finally {
        uploading.value = false
      }
    }

    function onFile(e) {
      handleFile(e.target.files[0])
      e.target.value = ''
    }

    function onDrop(e) {
      dragHover.value = false
      handleFile(e.dataTransfer.files[0])
    }

    function clearCand() {
      cand.value = null
      match.value = null
      disposeChart()
    }

    function onResize() {
      chart?.resize()
    }

    onMounted(async () => {
      window.addEventListener('resize', onResize)
      try {
        jobList.value = await jobs.list('approved')
      } catch (e) {
        error.value = e.message
      } finally {
        loadingJobs.value = false
      }
      // 从面试流程带 job 参数跳转过来且已有会话简历 → 自动生成
      if (canGenerate.value) generate()
    })

    onBeforeUnmount(() => {
      disposed = true
      window.removeEventListener('resize', onResize)
      disposeChart()
    })

    return {
      state,
      cand,
      jobList,
      jobId,
      jobTitle,
      loadingJobs,
      loading,
      uploading,
      dragHover,
      error,
      match,
      canGenerate,
      scoreClass,
      chartEl,
      generate,
      onFile,
      onDrop,
      clearCand,
    }
  },
}
</script>

<style scoped>
.match-page {
  min-height: 100vh;
  max-width: 860px;
  margin: 0 auto;
  padding: 20px 20px 50px;
}

.topbar {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.back {
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.page-title {
  font-size: 17px;
  color: #1a3a63;
}

.panel {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 22px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
  margin-bottom: 16px;
}

.panel h2 {
  font-size: 15px;
  color: #2c3e50;
  margin-bottom: 12px;
}

.cand-line {
  font-size: 14px;
  color: #4b5a6a;
  display: flex;
  align-items: center;
  gap: 12px;
}

.cand-line b {
  color: #1a3a63;
}

.upload-zone {
  text-align: center;
  padding: 26px 16px;
  border: 2px dashed #cdd9ea;
  background: #f9fbfe;
  border-radius: 10px;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.upload-zone.hover {
  border-color: #1a73e8;
  background: #eff6ff;
}

.sub {
  font-size: 13px;
  color: #6b7a8d;
  line-height: 1.8;
}

button.ghost {
  border: 1px solid #dde3ec;
  background: #fff;
  border-radius: 999px;
  padding: 7px 18px;
  font-size: 13px;
  color: #5f6b7a;
  cursor: pointer;
}

button.ghost:hover {
  border-color: #1a73e8;
  color: #1a73e8;
}

.job-select {
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  border: 1px solid #dde3ec;
  border-radius: 10px;
  color: #2c3e50;
  background: #fff;
  margin-bottom: 4px;
}

button.primary {
  margin-top: 12px;
  width: 100%;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  color: #fff;
  padding: 12px;
  font-size: 15px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
}

button.primary:disabled {
  background: #c6d4e8;
  box-shadow: none;
  cursor: not-allowed;
}

.dots-line {
  margin-top: 12px;
  font-size: 13px;
  color: #8a97a8;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.dots {
  display: inline-flex;
  gap: 4px;
}

.dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #4f9cf9;
  animation: bounce 1.2s infinite ease-in-out;
}

.dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-5px); opacity: 1; }
}

/* 评审单 */
.score-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 6px;
}

.big-score {
  font-size: 44px;
  font-weight: 800;
  width: 92px;
  height: 92px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.big-score.high { background: #e8f5e9; color: #1a7f37; }
.big-score.mid { background: #fff7e6; color: #b26a00; }
.big-score.low { background: #fdecea; color: #e5533d; }

.score-cap b {
  font-size: 14px;
  color: #2c3e50;
}

.score-cap p {
  font-size: 13px;
  color: #6b7a8d;
  line-height: 1.7;
  margin-top: 4px;
}

.chart {
  height: 300px;
}

.hl-gap {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 8px;
}

.hl h3, .gap h3 {
  font-size: 13px;
  margin-bottom: 6px;
}

.hl h3 { color: #1a7f37; }
.gap h3 { color: #b26a00; }

.hl ul, .gap ul {
  padding-left: 16px;
}

.hl li, .gap li {
  font-size: 12.5px;
  color: #4b5a6a;
  line-height: 1.8;
}

.to-interview {
  display: inline-block;
  margin-top: 16px;
  font-size: 13px;
  color: #1a73e8;
  text-decoration: none;
}

.to-interview:hover {
  text-decoration: underline;
}

.err {
  margin-top: 12px;
  font-size: 13px;
  color: #e5533d;
}

@media (max-width: 640px) {
  .match-page {
    padding: 14px 12px 40px;
  }

  .hl-gap {
    grid-template-columns: 1fr;
  }
}
</style>
