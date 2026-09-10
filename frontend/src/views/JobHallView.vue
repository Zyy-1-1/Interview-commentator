<template>
  <div class="hall-page">
    <section class="hero">
      <p class="hero-kicker">面评家 · 可信职业陪练</p>
      <h1>先练一次，再决定怎么投</h1>
      <p class="hero-intro">选一个真实岗位，和 AI 面试官完成一轮有反馈的模拟面试，把准备方向变成下一步行动。</p>
      <ul class="trust-list" aria-label="模拟面试说明">
        <li><span class="trust-icon" aria-hidden="true">15</span><span>约 15 分钟完成一次模拟</span></li>
        <li><span class="trust-icon" aria-hidden="true">↗</span><span>根据回答动态追问，不走固定题库</span></li>
        <li><span class="trust-icon" aria-hidden="true">✓</span><span>报告附回答证据，可回看与复盘</span></li>
        <li><span class="trust-icon" aria-hidden="true">⌫</span><span>简历原文件解析后删除</span></li>
      </ul>
    </section>

    <!-- 筛选条:类别与关键词走 URL query,其余条件保持在大厅本地 -->
    <section class="filters">
      <div class="filter-heading">
        <div>
          <p class="section-kicker">岗位大厅</p>
          <h2>按条件找岗位</h2>
        </div>
        <p class="result-count"><b>{{ state.jobs.length }}</b> 个岗位</p>
      </div>
      <div class="filters-row">
        <div class="field">
          <label for="category-filter">岗位类别</label>
          <select id="category-filter" v-model="filters.category" @change="syncCategory">
            <option value="">全部类别</option>
            <option v-for="c in facets.categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field">
          <label for="recruit-type-filter">招聘类型</label>
          <select id="recruit-type-filter" v-model="filters.recruit_type" @change="load">
            <option value="">全部</option>
            <option v-for="c in facets.recruit_types" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field">
          <label for="education-filter">学历要求</label>
          <select id="education-filter" v-model="filters.education" @change="load">
            <option value="">全部</option>
            <option v-for="c in facets.educations" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field">
          <label for="salary-filter">期望月薪(起)</label>
          <input
            id="salary-filter"
            v-model.number="filters.salary_min"
            type="number"
            min="0"
            placeholder="如 20"
            class="num"
            @change="load"
          />
        </div>
        <div class="field grow">
          <label for="major-filter">专业</label>
          <input
            id="major-filter"
            v-model.trim="filters.major"
            type="text"
            placeholder="如 计算机 / 电气…"
            @input="debouncedLoad"
          />
        </div>
        <button v-if="hasFilter" class="reset" @click="resetFilters">清除筛选</button>
      </div>
      <p class="active-filters">
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
          <div class="title-row">
            <h2 class="title">{{ j.title }}</h2>
            <span v-if="j.is_official" class="badge">官方</span>
          </div>
          <div class="key-info">
            <span class="company">{{ j.company || '面评家官方岗位' }}</span>
            <span v-if="j.salary_min || j.salary_max" class="salary">{{ salaryText(j) }}</span>
            <span v-if="j.location" class="location"><span aria-hidden="true">⌖</span> {{ j.location }}</span>
          </div>
        </div>
        <p class="jd">{{ (j.jd_text || '').slice(0, 90) }}…</p>
        <div class="tags">
          <span class="chip cat" v-if="j.category">{{ j.category }}</span>
          <span class="chip rec" v-if="j.recruit_type">{{ j.recruit_type }}</span>
          <span class="chip edu" v-if="j.education">{{ j.education }}</span>
        </div>
        <p class="meta" v-if="j.majors">
          <span class="mj">专业：{{ j.majors }}</span>
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
          >模拟这个岗位</router-link>
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
    const facets = reactive({ categories: [], educations: [], recruit_types: [] })
    // q / category 来自 URL query(外壳顶栏搜索、大厅类别筛选写入)
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

    function syncCategory() {
      const query = { ...route.query }
      if (filters.category) query.category = filters.category
      else delete query.category
      router.replace({ path: '/', query })
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
        facets.categories = f.categories || []
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
      syncCategory,
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
  padding: 22px 24px 20px;
  margin-bottom: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.hero-kicker,
.section-kicker {
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-kicker {
  margin-bottom: var(--space-2);
}

.hero h1 {
  max-width: 22em;
  font-size: clamp(24px, 3.4vw, 32px);
  line-height: 1.25;
  color: var(--color-ink);
  margin-bottom: var(--space-2);
}

.hero-intro {
  max-width: 58em;
  font-size: 13px;
  color: var(--color-muted);
}

.trust-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  list-style: none;
  margin-top: var(--space-5);
}

.trust-list li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  color: var(--color-text);
  font-size: 12px;
  line-height: 1.45;
}

.trust-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  flex: 0 0 26px;
  border: 1px solid #bfd4e8;
  border-radius: var(--radius-pill);
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-size: 10px;
  font-weight: 700;
}

/* 筛选条 */
.filters {
  min-width: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  margin-bottom: var(--space-5);
  box-shadow: var(--shadow-card);
}

.filter-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.filter-heading h2 {
  margin-top: 2px;
  color: var(--color-ink);
  font-size: 17px;
  line-height: 1.3;
}

.result-count,
.active-filters {
  color: var(--color-subtle);
  font-size: 12px;
}

.result-count {
  white-space: nowrap;
}

.result-count b {
  color: var(--color-primary);
  font-size: 15px;
}

.active-filters {
  min-height: 18px;
  margin-top: var(--space-3);
}

.active-filters span + span {
  margin-left: var(--space-1);
}

.filters-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  align-items: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.field.grow {
  grid-column: span 2;
}

.field label {
  font-size: 11px;
  color: var(--color-muted);
}

.field select,
.field input {
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: 9px 10px;
  font-size: 13px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: var(--color-surface);
}

.field select:focus,
.field input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.field input.num {
  max-width: none;
}

button.reset {
  align-self: flex-end;
  min-height: 44px;
  border: 1px solid var(--color-border-strong);
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  padding: 9px 14px;
  font-size: 13px;
  color: var(--color-danger);
  cursor: pointer;
  white-space: nowrap;
}

button.reset:hover {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

/* 卡片 */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
  gap: var(--space-4);
  min-width: 0;
}

.card {
  min-width: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  box-shadow: var(--shadow-card);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
}

.card-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.title-row,
.key-info {
  display: flex;
  align-items: center;
  min-width: 0;
}

.title-row {
  gap: var(--space-2);
}

.key-info {
  flex-wrap: wrap;
  gap: var(--space-2);
}

.title {
  font-size: 16px;
  line-height: 1.4;
  color: var(--color-ink);
  min-width: 0;
  overflow-wrap: anywhere;
}

.badge {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border: 1px solid #eed6a7;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.company {
  font-size: 12px;
  color: var(--color-muted);
  font-weight: 600;
}

.salary {
  color: var(--color-primary-strong);
  font-size: 13px;
  font-weight: 700;
}

.location {
  color: var(--color-muted);
  font-size: 12px;
}

.jd {
  font-size: 13px;
  color: var(--color-text);
  line-height: 1.6;
  flex: 1;
  overflow-wrap: anywhere;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  font-size: 11px;
  padding: 3px 9px;
  border-radius: var(--radius-pill);
}

.chip.cat { color: var(--color-primary-strong); background: var(--color-primary-soft); }
.chip.rec { color: #6b4b9e; background: #f1ecfa; }
.chip.edu { color: var(--color-success); background: var(--color-success-soft); }

.meta {
  font-size: 11.5px;
  color: var(--color-subtle);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.meta .mj {
  color: var(--color-subtle);
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  border-top: 1px solid var(--color-border);
  padding-top: var(--space-3);
}

.dim-count {
  font-size: 12px;
  color: var(--color-subtle);
}

.dim-count.warn {
  color: var(--color-warning);
}

.go {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: var(--color-primary);
  text-decoration: none;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.go.disabled {
  background: #b9c9d9;
  box-shadow: none;
  pointer-events: none;
}

.tip {
  text-align: center;
  color: var(--color-subtle);
  padding: 60px 0;
  font-size: 14px;
}

.tip.err {
  color: var(--color-danger);
}

.tip a {
  color: var(--color-primary);
}

@media (max-width: 860px) {
  .trust-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filters-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .field.grow {
    grid-column: 1 / -1;
  }

  button.reset {
    width: 100%;
    grid-column: 1 / -1;
  }
}

@media (max-width: 520px) {
  .hero {
    padding: 18px 16px;
  }

  .hero h1 {
    font-size: 24px;
  }

  .trust-list {
    grid-template-columns: 1fr;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }

  .filters {
    padding: var(--space-3);
  }

  .filter-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-1);
  }

  .card {
    padding: var(--space-4);
  }

  .card-foot {
    align-items: stretch;
    flex-direction: column;
  }

  .go {
    width: 100%;
  }
}
</style>
