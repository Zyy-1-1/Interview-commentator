<template>
  <div class="match-page">
    <header class="page-heading">
      <p class="eyebrow">简历评审</p>
      <h1 class="page-title">先看清匹配度，再决定怎么准备</h1>
      <p>AI 会按岗位考察维度比对简历，给出优势、缺口和下一步练习方向。</p>
    </header>

    <div class="setup-grid">
      <!-- 简历来源:本会话已上传 或 现场上传 -->
      <section class="panel step-panel">
        <div class="step-title"><span>1</span><div><h2>选择评审简历</h2><p>原文件提取完成后立即删除</p></div></div>
        <template v-if="cand">
          <div class="cand-line">
            <div><small>本次使用</small><b>{{ cand.name || '(未识别姓名)' }}</b></div>
            <button class="ghost" @click="clearCand">更换简历</button>
          </div>
        </template>
        <template v-else>
          <div class="upload-zone" :class="{ hover: dragHover }"
            @dragover.prevent="dragHover = true" @dragleave="dragHover = false"
            @drop.prevent="onDrop">
            <span class="upload-icon" aria-hidden="true">↑</span>
            <p class="sub">PDF / DOCX / Markdown / TXT，最大 10 MB</p>
            <button class="ghost" :disabled="uploading" @click="$refs.file.click()">
              {{ uploading ? '正在解析…' : '选择简历文件' }}
            </button>
            <input ref="file" type="file" accept=".pdf,.docx,.txt,.md" hidden @change="onFile" />
          </div>
        </template>
      </section>

      <!-- 岗位选择 -->
      <section class="panel step-panel">
        <div class="step-title"><span>2</span><div><h2>选择目标岗位</h2><p>评审标准来自岗位考察维度</p></div></div>
        <p v-if="loadingJobs" class="sub loading-line">正在加载可用岗位…</p>
        <label v-else class="select-field">
          <span>目标岗位</span>
          <select v-model="jobId" class="job-select">
            <option :value="0" disabled>请选择岗位</option>
            <option v-for="j in jobList" :key="j.id" :value="j.id">
              {{ j.title }} · {{ j.company || '面评家官方岗位' }}
            </option>
          </select>
        </label>
        <button class="primary" :disabled="!canGenerate || loading" @click="generate">
          {{ loading ? 'AI 正在逐维度比对…' : '生成匹配评审' }}
        </button>
        <p v-if="loading" class="dots-line">
          正在比对简历与岗位要求 <span class="dots"><i></i><i></i><i></i></span>
        </p>
      </section>
    </div>
    <div v-if="error" class="error-panel" role="alert"><b>暂时无法完成评审</b><span>{{ error }}</span></div>

    <!-- 评审单 -->
    <section class="panel result-panel" v-if="match">
      <div class="result-heading">
        <div><p class="eyebrow">匹配结果</p><h2>{{ jobTitle }}</h2></div>
        <router-link v-if="jobId" class="to-interview" :to="`/apply/${jobId}`">开始针对性模拟面试</router-link>
      </div>
      <div class="score-row">
        <div class="big-score" :class="scoreClass"><b>{{ match.overall }}</b><span>/ 100</span></div>
        <div class="score-cap">
          <span>整体匹配度</span>
          <p>{{ match.summary }}</p>
        </div>
      </div>
      <div class="result-grid">
        <div class="chart-wrap"><h3>岗位维度画像</h3><div ref="chartEl" class="chart"></div></div>
        <div class="hl-gap">
          <div class="hl">
            <h3>已具备的优势</h3>
            <ul><li v-for="(h, i) in match.highlights" :key="i">{{ h }}</li></ul>
          </div>
          <div class="gap">
            <h3>优先补强项</h3>
            <ul><li v-for="(g, i) in match.gaps" :key="i">{{ g }}</li></ul>
          </div>
        </div>
      </div>
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
    let requestVersion = 0

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
      const version = ++requestVersion
      loading.value = true
      error.value = ''
      disposeChart()
      match.value = null
      try {
        const result = await candidates.match(cand.value.id, jobId.value, cand.value.accessToken)
        if (disposed || version !== requestVersion) return
        match.value = result
        await nextTick()
        if (!disposed && version === requestVersion) renderChart()
      } catch (e) {
        if (!disposed && version === requestVersion) error.value = e.message
      } finally {
        if (!disposed && version === requestVersion) loading.value = false
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
      requestVersion += 1
      loading.value = false
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
      requestVersion += 1
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
  max-width: 960px;
  min-width: 0;
}

.page-heading { margin: 6px 0 22px; }
.page-heading .eyebrow,
.result-heading .eyebrow { color: var(--brand-700, #1d4ed8); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.page-title {
  margin-top: 5px;
  font-size: clamp(24px, 3.4vw, 31px);
  color: var(--text-strong, #17233c);
  letter-spacing: -.02em;
}
.page-heading > p:last-child { margin-top: 8px; color: var(--text-muted, #64748b); font-size: 14px; line-height: 1.7; }

.setup-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }

.panel {
  background: #fff;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: var(--radius-lg, 14px);
  padding: 22px;
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(15, 23, 42, .05));
}

.panel h2 {
  font-size: 15px;
  color: #2c3e50;
  margin-bottom: 12px;
}

.step-title { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.step-title > span { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 50%; background: var(--brand-50, #eff6ff); color: var(--brand-700, #1d4ed8); font-weight: 750; }
.step-title h2 { margin: 0; }
.step-title p { margin-top: 2px; color: var(--text-muted, #64748b); font-size: 12px; }

.cand-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 118px;
  padding: 18px;
  border: 1px solid var(--border-subtle, #edf1f6);
  border-radius: 12px;
  background: var(--surface-subtle, #f8fafc);
}
.cand-line small { display: block; color: var(--text-muted, #64748b); margin-bottom: 4px; }
.cand-line b { display: block; color: var(--text-strong, #17233c); font-size: 16px; }

.upload-zone {
  text-align: center;
  min-height: 118px;
  padding: 18px 16px;
  border: 1px dashed var(--border-strong, #c7d2e0);
  background: var(--surface-subtle, #f8fafc);
  border-radius: 12px;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.upload-icon { display: grid; width: 30px; height: 30px; margin: 0 auto 6px; place-items: center; border-radius: 9px; background: var(--brand-50, #eff6ff); color: var(--brand-700, #1d4ed8); font-weight: 800; }

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
  min-height: 44px;
  border: 1px solid var(--border-strong, #c7d2e0);
  background: #fff;
  border-radius: 999px;
  padding: 7px 18px;
  font-size: 13px;
  color: var(--text, #334155);
  cursor: pointer;
}

button.ghost:hover {
  border-color: #1a73e8;
  color: #1a73e8;
}

.job-select {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  font-size: 14px;
  border: 1px solid var(--border-strong, #c7d2e0);
  border-radius: 10px;
  color: #2c3e50;
  background: #fff;
  margin-top: 6px;
}
.select-field > span { color: var(--text-muted, #64748b); font-size: 12px; font-weight: 650; }
.loading-line { min-height: 104px; display: grid; place-items: center; }

button.primary {
  margin-top: 12px;
  width: 100%;
  border: none;
  min-height: 44px;
  border-radius: var(--radius-md, 10px);
  background: var(--brand-600, #2563eb);
  color: #fff;
  padding: 12px;
  font-size: 15px;
  cursor: pointer;
  box-shadow: none;
}

.error-panel { display: flex; flex-direction: column; gap: 3px; margin: 0 0 16px; padding: 13px 16px; border: 1px solid var(--danger-200, #fecaca); border-left: 3px solid var(--danger-600, #dc2626); border-radius: 10px; background: var(--danger-50, #fef2f2); color: var(--danger-800, #991b1b); font-size: 13px; line-height: 1.6; }

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
.result-panel { margin-top: 20px; }
.result-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.result-heading h2 { margin: 5px 0 0; font-size: 22px; }
.score-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  margin-bottom: 20px;
  border-radius: 12px;
  background: var(--brand-50, #eff6ff);
}

.big-score {
  width: 104px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.big-score b { font-size: 45px; line-height: 1; }
.big-score span { margin-top: 5px; font-size: 11px; color: var(--text-muted, #64748b); font-weight: 650; }

.big-score.high { color: var(--success-700, #15803d); }
.big-score.mid { color: var(--warning-700, #b45309); }
.big-score.low { color: var(--danger-700, #b91c1c); }

.score-cap > span {
  font-size: 14px;
  color: var(--text-strong, #17233c);
  font-weight: 700;
}

.result-grid { display: grid; grid-template-columns: minmax(300px, .9fr) minmax(0, 1.1fr); gap: 18px; }
.chart-wrap { min-width: 0; border: 1px solid var(--border-subtle, #edf1f6); border-radius: 12px; padding: 16px; }
.chart-wrap h3 { color: var(--text-strong, #17233c); font-size: 14px; }

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
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hl, .gap { flex: 1; padding: 16px; border: 1px solid var(--border-subtle, #edf1f6); border-radius: 12px; }

.hl h3, .gap h3 {
  font-size: 13px;
  margin-bottom: 6px;
}

.hl h3 { color: var(--success-700, #15803d); }
.gap h3 { color: var(--warning-800, #92400e); }

.hl ul, .gap ul {
  padding-left: 16px;
}

.hl li, .gap li {
  font-size: 12.5px;
  color: #4b5a6a;
  line-height: 1.8;
}

.to-interview {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  padding: 0 16px;
  border-radius: 10px;
  background: var(--brand-600, #2563eb);
  font-size: 14px;
  font-weight: 700;
  color: #fff;
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
  .page-heading { margin-top: 0; }
  .setup-grid,
  .result-grid { grid-template-columns: 1fr; }
  .panel { padding: 18px; }
  .result-heading { align-items: flex-start; flex-direction: column; }
  .to-interview { width: 100%; justify-content: center; }
  .score-row { align-items: flex-start; padding: 16px 12px; }
  .big-score { width: 82px; }
  .big-score b { font-size: 38px; }
  .chart { height: 270px; }
  .cand-line { align-items: flex-start; flex-direction: column; }
  .cand-line .ghost { width: 100%; }
}
</style>
