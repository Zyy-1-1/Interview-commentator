<template>
  <div class="hall-page">
    <section class="hero">
      <h1>选一个岗位，先让 AI 面试官面你一次</h1>
      <p>上传简历 → 与数字人面试官模拟对话 → 拿到你的专属竞争力报告（简历评审单可在「简历评审」页查看）</p>
    </section>

    <!-- 辅助筛选条(类别与关键词由外壳的侧栏/顶栏驱动,走 URL query) -->
    <section class="filters">
      <div class="filters-row">
        <div class="field">
          <label>招聘类型</label>
          <select v-model="filters.recruit_type" @change="load">
            <option value="">全部</option>
            <option v-for="c in facets.recruit_types" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field">
          <label>学历要求</label>
          <select v-model="filters.education" @change="load">
            <option value="">全部</option>
            <option v-for="c in facets.educations" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field">
          <label>期望月薪(起)</label>
          <input
            v-model.number="filters.salary_min"
            type="number"
            min="0"
            placeholder="如 20"
            class="num"
            @change="load"
          />
        </div>
        <div class="field grow">
          <label>专业</label>
          <input
            v-model.trim="filters.major"
            type="text"
            placeholder="如 计算机 / 电气…"
            @input="debouncedLoad"
          />
        </div>
        <button v-if="hasFilter" class="reset" @click="resetFilters">清除筛选</button>
      </div>
      <p class="result-count">
        <b>{{ state.jobs.length }}</b> 个岗位
        <span v-if="filters.category">· 类别「{{ filters.category }}」</span>
        <span v-if="filters.q">· 搜索「{{ filters.q }}」</span>
        <span v-if="hasFilter">(已筛选)</span>
      </p>
    </section>

    <p v-if="state.loading" class="tip">加载岗位中…</p>
    <p v-else-if="state.error" class="tip err">{{ state.error }}</p>
    <div v-else-if="!state.jobs.length" class="tip">
      没有符合条件的岗位,试试<router-link to="/" @click.prevent="resetFilters">清除筛选</router-link>
    </div>
    <div v-else class="grid">
      <article v-for="j in state.jobs" :key="j.id" class="card">
        <div class="card-head">
          <h2 class="title">
            {{ j.title }}
            <span v-if="j.is_official" class="badge">官方</span>
          </h2>
          <span class="company">{{ j.company || '面评家官方岗位' }}</span>
        </div>
        <p class="jd">{{ (j.jd_text || '').slice(0, 90) }}…</p>
        <div class="tags">
          <span class="chip cat" v-if="j.category">{{ j.category }}</span>
          <span class="chip rec" v-if="j.recruit_type">{{ j.recruit_type }}</span>
          <span class="chip edu" v-if="j.education">{{ j.education }}</span>
          <span class="chip sal" v-if="j.salary_min || j.salary_max">
            {{ salaryText(j) }}
          </span>
        </div>
        <p class="meta" v-if="j.location || j.majors">
          <span v-if="j.location">📍 {{ j.location }}</span>
          <span v-if="j.majors" class="mj"> · 专业:{{ j.majors }}</span>
        </p>
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
  </div>
</template>

<script>
import { computed, onMounted, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { jobs } from '../api'

export default {
  name: 'JobHallView',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const state = reactive({ jobs: [], loading: true, error: '' })
    const facets = reactive({ educations: [], recruit_types: [] })
    // q / category 来自 URL query(外壳顶栏搜索、侧栏类别筛选写入)
    const filters = reactive({
      q: String(route.query.q || ''),
      category: String(route.query.category || ''),
      recruit_type: '',
      education: '',
      salary_min: '',
      major: '',
    })

    const hasFilter = computed(() =>
      Object.values(filters).some((v) => v !== '' && v != null)
    )

    // 外壳改 query(搜索/类别点击/清除)时同步并重查
    watch(
      () => [String(route.query.q || ''), String(route.query.category || '')],
      ([q, c]) => {
        if (q === filters.q && c === filters.category) return
        filters.q = q
        filters.category = c
        load()
      }
    )

    let timer = null
    function debouncedLoad() {
      clearTimeout(timer)
      timer = setTimeout(load, 300)
    }

    function salaryText(j) {
      const lo = j.salary_min
      const hi = j.salary_max
      const range = lo && hi ? `${lo}-${hi}K` : hi ? `≤${hi}K` : `${lo}K+`
      return j.salary_months && j.salary_months !== 12
        ? `${range}·${j.salary_months}薪`
        : range
    }

    async function load() {
      state.loading = true
      state.error = ''
      try {
        state.jobs = await jobs.search(filters)
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    function resetFilters() {
      filters.recruit_type = ''
      filters.education = ''
      filters.salary_min = ''
      filters.major = ''
      if (route.query.q || route.query.category) {
        // query 清掉后 watch 会触发重查,避免双查
        router.replace({ path: '/', query: {} })
      } else {
        load()
      }
    }

    function go(j) {
      if (!j.dimensions || !j.dimensions.length) return
      router.push(`/apply/${j.id}`)
    }

    onMounted(async () => {
      try {
        const f = await jobs.facets()
        facets.educations = f.educations || []
        facets.recruit_types = f.recruit_types || []
      } catch (e) {
        /* facets 失败不阻断大厅加载 */
      }
      load()
    })

    return {
      state,
      facets,
      filters,
      hasFilter,
      load,
      debouncedLoad,
      resetFilters,
      go,
      salaryText,
    }
  },
}
</script>

<style scoped>
.hero {
  padding: 6px 2px 14px;
}

.hero h1 {
  font-size: clamp(19px, 3.4vw, 24px);
  color: #1a3a63;
  margin-bottom: 6px;
}

.hero p {
  font-size: 13px;
  color: #6b7a8d;
}

/* 筛选条 */
.filters {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 12px 16px;
  margin-bottom: 16px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
}

.filters-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 110px;
}

.field.grow {
  flex: 2;
  min-width: 150px;
}

.field label {
  font-size: 11px;
  color: #8a97a8;
}

.field select,
.field input {
  padding: 8px 10px;
  font-size: 13px;
  border: 1px solid #dde3ec;
  border-radius: 9px;
  color: #2c3e50;
  background: #fff;
}

.field select:focus,
.field input:focus {
  outline: none;
  border-color: #1a73e8;
}

.field input.num {
  max-width: 100px;
}

button.reset {
  align-self: flex-end;
  border: 1px solid #dde3ec;
  background: #fff;
  border-radius: 9px;
  padding: 8px 14px;
  font-size: 13px;
  color: #e5533d;
  cursor: pointer;
  white-space: nowrap;
}

button.reset:hover {
  border-color: #e5533d;
}

.result-count {
  margin-top: 10px;
  font-size: 12px;
  color: #8a97a8;
}

.result-count b {
  color: #1a73e8;
}

/* 卡片 */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
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
  display: flex;
  align-items: center;
  gap: 6px;
}

.badge {
  font-size: 10px;
  font-weight: 600;
  color: #b26a00;
  background: #fff3d6;
  border: 1px solid #ffe0a3;
  padding: 1px 6px;
  border-radius: 5px;
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

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  font-size: 11px;
  padding: 3px 9px;
  border-radius: 999px;
}

.chip.cat { color: #1a73e8; background: #e8f1fd; }
.chip.rec { color: #7a3ff2; background: #f0e9fd; }
.chip.edu { color: #2e9e6b; background: #e6f6ee; }
.chip.sal { color: #c2410c; background: #feeadd; font-weight: 600; }

.meta {
  font-size: 11.5px;
  color: #8a97a8;
  line-height: 1.5;
}

.meta .mj {
  color: #9aa5b1;
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

@media (max-width: 860px) {
  .field,
  .field.grow {
    min-width: 46%;
  }

  button.reset {
    width: 100%;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
