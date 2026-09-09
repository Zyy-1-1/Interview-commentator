<template>
  <div class="shell">
    <!-- 顶栏:品牌 + 大厅搜索 -->
    <header class="topbar">
      <div class="topbar-inner">
        <router-link class="brand" to="/">
          <span class="brand-dot">🎙</span>
          <div class="brand-text">
            <span class="brand-name">面评家</span>
            <span class="brand-sub">AI 模拟面试官 · 个人竞争力报告</span>
          </div>
        </router-link>
        <input
          v-if="isHall"
          v-model.trim="q"
          class="search"
          type="search"
          placeholder="搜索岗位 / 公司 / 关键词…"
          @input="debouncedSyncQ"
        />
      </div>
    </header>

    <div class="layout">
      <!-- 侧栏:功能导航(+ 大厅页时的岗位类别快捷筛选) -->
      <aside class="side">
        <nav class="menu">
          <router-link class="menu-item" to="/" exact-active-class="cur">岗位大厅</router-link>
          <router-link class="menu-item" to="/match" active-class="cur">简历评审</router-link>
          <router-link class="menu-item" to="/community" active-class="cur">交流区</router-link>
          <router-link class="menu-item" to="/jobs/submit" active-class="cur">发布招聘信息</router-link>
          <router-link class="menu-item" to="/review" active-class="cur">官方审核</router-link>
        </nav>
        <template v-if="isHall">
          <div class="side-sep"></div>
          <div class="side-block">
            <h3 class="side-title">岗位类别</h3>
            <router-link class="cat" :class="{ on: !activeCat }" :to="catLink('')">全部</router-link>
            <router-link
              v-for="c in categories"
              :key="c"
              class="cat"
              :class="{ on: activeCat === c }"
              :to="catLink(c)"
            >{{ c }}</router-link>
          </div>
        </template>
      </aside>

      <!-- 主区:功能页在此渲染 -->
      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { jobs } from '../api'

export default {
  name: 'AppShell',
  setup() {
    const route = useRoute()
    const router = useRouter()

    const isHall = computed(() => route.name === 'hall')
    const categories = ref([])
    const q = ref(String(route.query.q || ''))
    const activeCat = computed(() => String(route.query.category || ''))

    function catLink(c) {
      const query = {}
      if (c) query.category = c
      if (q.value) query.q = q.value
      return { path: '/', query }
    }

    // 搜索词经 URL query 传给大厅子路由(debounce 避免每键一次路由重写)
    let timer = null
    function debouncedSyncQ() {
      clearTimeout(timer)
      timer = setTimeout(() => {
        const query = { ...route.query }
        if (q.value) query.q = q.value
        else delete query.q
        router.replace({ path: '/', query })
      }, 300)
    }
    // 大厅「清除筛选」等场景改了 query 时,回写搜索框
    watch(
      () => route.query.q || '',
      (v) => {
        if (v !== q.value) q.value = v
      }
    )

    onMounted(async () => {
      try {
        const f = await jobs.facets()
        categories.value = f.categories || []
      } catch {
        /* 类别筛选拉取失败不阻断页面 */
      }
    })

    return { isHall, categories, q, activeCat, catLink, debouncedSyncQ }
  },
}
</script>

<style scoped>
.shell {
  min-height: 100vh;
  background: #f5f7fb;
}

/* ---------------- header ---------------- */
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: #fff;
  border-bottom: 1px solid #e4e9f0;
}

.topbar-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
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

.search {
  flex: 0 1 360px;
  min-width: 200px;
  padding: 9px 14px;
  font-size: 13.5px;
  border: 1px solid #dde3ec;
  border-radius: 999px;
  color: #2c3e50;
  background: #f7f9fc;
}

.search:focus {
  outline: none;
  border-color: #1a73e8;
  background: #fff;
}

/* ---------------- 三栏骨架 ---------------- */
.layout {
  max-width: 1200px;
  margin: 0 auto;
  padding: 18px 20px 44px;
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

/* ---------------- aside ---------------- */
.side {
  position: sticky;
  top: 74px;
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 12px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.menu-item {
  display: block;
  padding: 9px 12px;
  border-radius: 9px;
  font-size: 14px;
  color: #445468;
  text-decoration: none;
}

.menu-item:hover {
  background: #eef4fd;
  color: #1a73e8;
}

.menu-item.cur {
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 3px 8px rgba(26, 115, 232, 0.3);
}

.side-sep {
  border-top: 1px solid #eef1f5;
  margin: 10px 0;
}

.side-title {
  font-size: 12px;
  color: #8a97a8;
  font-weight: 600;
  padding: 0 4px 6px;
}

.side-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
}

.cat {
  text-align: left;
  border: none;
  background: none;
  padding: 7px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: #5f6b7a;
  cursor: pointer;
  text-decoration: none;
}

.cat:hover {
  background: #eef4fd;
  color: #1a73e8;
}

.cat.on {
  background: #e8f1fd;
  color: #1a73e8;
  font-weight: 600;
}

/* ---------------- main ---------------- */
.main {
  min-width: 0;
}

/* ---------------- 响应式 ---------------- */
@media (max-width: 860px) {
  .layout {
    grid-template-columns: 1fr;
    padding: 14px 12px 36px;
  }

  .side {
    position: static;
  }

  .menu {
    flex-direction: row;
    overflow-x: auto;
    gap: 8px;
    padding-bottom: 2px;
  }

  .menu-item {
    white-space: nowrap;
    padding: 8px 14px;
  }

  .side-block {
    flex-direction: row;
    flex-wrap: wrap;
    max-height: none;
    overflow: visible;
  }

  .topbar-inner {
    padding: 10px 12px;
  }

  .search {
    flex: 1 1 100%;
    order: 3;
  }
}
</style>
