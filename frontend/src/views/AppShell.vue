<template>
  <div class="shell">
    <!-- 顶栏:品牌 + 大厅搜索 -->
    <header class="topbar">
      <div class="topbar-inner">
        <router-link class="brand" to="/">
          <span class="brand-dot" aria-hidden="true">⌁</span>
          <div class="brand-text">
            <span class="brand-name">面评家</span>
            <span class="brand-sub">可信的 AI 职业陪练</span>
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
      <!-- 侧栏:候选人主导航与次级服务入口 -->
      <aside class="side">
        <nav class="menu" aria-label="功能导航">
          <div class="menu-group menu-primary">
            <span class="menu-label">候选人空间</span>
            <router-link class="menu-item" to="/" exact-active-class="cur">岗位大厅</router-link>
            <router-link class="menu-item" to="/match" active-class="cur">简历评审</router-link>
            <router-link class="menu-item" to="/community" active-class="cur">交流区</router-link>
          </div>
          <div class="menu-group menu-secondary">
            <span class="menu-label">服务入口</span>
            <router-link class="menu-item" to="/jobs/submit" active-class="cur">发布招聘信息</router-link>
            <router-link class="menu-item" to="/review" active-class="cur">官方审核</router-link>
          </div>
        </nav>
      </aside>

      <!-- 主区:功能页在此渲染 -->
      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export default {
  name: 'AppShell',
  setup() {
    const route = useRoute()
    const router = useRouter()

    const isHall = computed(() => route.name === 'hall')
    const q = ref(String(route.query.q || ''))

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

    return { isHall, q, debouncedSyncQ }
  },
}
</script>

<style scoped>
.shell {
  min-height: 100vh;
  background: transparent;
}

/* ---------------- header ---------------- */
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid var(--color-border);
}

.topbar-inner {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: var(--space-3) var(--space-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 44px;
  min-width: 0;
  flex: 1 1 auto;
  text-decoration: none;
}

.brand-dot {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
}

.brand-name {
  font-weight: 700;
  font-size: 18px;
  color: var(--color-ink);
}

.brand-sub {
  font-size: 11px;
  color: var(--color-subtle);
}

.search {
  flex: 0 1 360px;
  min-width: 0;
  width: min(360px, 100%);
  min-height: 44px;
  padding: 9px 14px;
  font-size: 13.5px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-pill);
  color: var(--color-text);
  background: var(--color-surface-soft);
}

.search:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-surface);
}

/* ---------------- 三栏骨架 ---------------- */
.layout {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 18px var(--space-5) 44px;
  display: grid;
  grid-template-columns: 212px minmax(0, 1fr);
  gap: var(--space-5);
  align-items: start;
}

/* ---------------- aside ---------------- */
.side {
  position: sticky;
  top: 74px;
  min-width: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.menu {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.menu-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.menu-label {
  padding: 2px 12px 5px;
  color: var(--color-subtle);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.menu-item {
  display: block;
  min-width: 0;
  min-height: 44px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--color-text);
  text-decoration: none;
}

.menu-item:hover {
  background: var(--color-primary-soft);
  color: var(--color-primary-strong);
}

.menu-item.cur {
  background: var(--color-primary);
  color: #fff;
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
    flex-direction: column;
    gap: var(--space-4);
  }

  .menu-group {
    width: 100%;
    flex: 0 1 auto;
  }

  .menu-item {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 44px;
    padding: 10px 12px;
    text-align: center;
  }

  .menu-primary,
  .menu-secondary {
    display: grid;
    gap: 4px;
  }

  .menu-primary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .menu-secondary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .menu-label {
    grid-column: 1 / -1;
  }

  .topbar-inner {
    padding: 10px 12px;
  }

  .search {
    flex: 1 1 100%;
    order: 3;
    width: 100%;
  }
}

@media (max-width: 520px) {
  .layout {
    padding: 12px 10px 32px;
  }

  .side {
    padding: 10px;
  }

  .menu {
    flex-direction: column;
    gap: var(--space-3);
  }

  .menu-group,
  .menu-secondary {
    width: 100%;
    flex-basis: auto;
  }

  .menu-primary {
    gap: 3px;
  }

  .menu-item {
    padding-inline: 6px;
    font-size: 13px;
  }
}
</style>
