<template>
  <div class="community">
    <header class="topbar">
      <div class="brand">
        <span class="brand-dot">🎙</span>
        <div class="brand-text">
          <span class="brand-name">面评家</span>
          <span class="brand-sub">AI 模拟面试官 · 个人竞争力报告</span>
        </div>
      </div>
      <nav class="nav">
        <router-link class="nav-link ghost" to="/">岗位大厅</router-link>
        <router-link class="nav-link ghost" to="/match">简历评审</router-link>
        <router-link class="nav-link" to="/community">交流区</router-link>
      </nav>
    </header>

    <section class="hero">
      <h1>应聘者交流区</h1>
      <p>面经分享 · offer 比较 · 薪资爆料,匿名发言(同一浏览器会话内昵称固定)</p>
      <p class="who" v-if="nickname">当前匿名身份:<b>{{ nickname }}</b></p>
    </section>

    <!-- 发帖框 -->
    <section class="composer">
      <input
        v-model.trim="form.title"
        class="ctitle"
        type="text"
        maxlength="100"
        placeholder="标题(2-100 字),如:刚面完腾讯后端,聊聊八股占比"
      />
      <textarea
        v-model.trim="form.content"
        class="cbody"
        rows="4"
        maxlength="5000"
        placeholder="说说你的面试经历、offer 纠结或想问的问题…"
      ></textarea>
      <div class="composer-foot">
        <span class="hint" v-if="submitError">{{ submitError }}</span>
        <span class="hint" v-else></span>
        <button class="publish" :disabled="submitting || !canPublish" @click="publish">
          {{ submitting ? '发布中…' : '发布' }}
        </button>
      </div>
    </section>

    <main class="body">
      <p v-if="state.loading" class="tip">加载帖子中…</p>
      <p v-else-if="state.error" class="tip err">{{ state.error }}</p>
      <div v-else-if="!state.posts.length" class="tip">还没有帖子,来发第一帖吧 👆</div>
      <div v-else class="list">
        <article
          v-for="p in state.posts"
          :key="p.id"
          class="post"
          @click="$router.push(`/community/${p.id}`)"
        >
          <div class="post-head">
            <h2 class="ptitle">{{ p.title }}</h2>
            <span class="like-cell" :class="{ mine: p.liked_by_me }">❤ {{ p.likes_count }}</span>
          </div>
          <p class="excerpt">{{ p.content }}</p>
          <div class="post-foot">
            <span class="author">{{ p.author_name }}</span>
            <span class="dot">·</span>
            <span class="time">{{ timeAgo(p.created_at) }}</span>
            <span class="spacer"></span>
            <span class="cm">💬 {{ p.comment_count }}</span>
          </div>
        </article>
      </div>
    </main>
  </div>
</template>

<script>
import { computed, onMounted, reactive, ref } from 'vue'
import { community } from '../api'
import { getCommunityToken } from '../access'
import { timeAgo } from '../format'

export default {
  name: 'CommunityView',
  setup() {
    const state = reactive({ posts: [], loading: true, error: '' })
    const form = reactive({ title: '', content: '' })
    const submitting = ref(false)
    const nickname = ref('')

    const canPublish = computed(
      () => form.title.length >= 2 && form.content.length >= 1 && !submitting.value
    )
    const submitError = computed(() => {
      if (form.title && form.title.length < 2) return '标题至少 2 个字'
      return ''
    })

    async function load() {
      state.loading = true
      state.error = ''
      try {
        state.posts = await community.list(getCommunityToken())
      } catch (e) {
        state.error = e.message
      } finally {
        state.loading = false
      }
    }

    async function publish() {
      if (!canPublish.value) return
      submitting.value = true
      state.error = ''
      try {
        await community.create(getCommunityToken(), form.title, form.content)
        form.title = ''
        form.content = ''
        await load()
      } catch (e) {
        state.error = e.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(async () => {
      try {
        const me = await community.me(getCommunityToken())
        nickname.value = me.nickname
      } catch {
        /* 昵称展示失败不阻断列表 */
      }
      load()
    })

    return {
      state,
      form,
      submitting,
      nickname,
      canPublish,
      submitError,
      publish,
      timeAgo,
    }
  },
}
</script>

<style scoped>
.community {
  min-height: 100vh;
  max-width: 860px;
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
  padding: 24px 16px 18px;
}

.hero h1 {
  font-size: clamp(20px, 4.4vw, 26px);
  color: #1a3a63;
  margin-bottom: 10px;
}

.hero p {
  font-size: 13.5px;
  color: #6b7a8d;
}

.hero .who {
  margin-top: 8px;
  font-size: 12.5px;
  color: #8a97a8;
}

.hero .who b {
  color: #1a73e8;
}

/* 发帖框 */
.composer {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 18px;
  box-shadow: 0 3px 12px rgba(30, 60, 110, 0.05);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ctitle,
.cbody {
  width: 100%;
  border: 1px solid #dde3ec;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 14px;
  color: #2c3e50;
  font-family: inherit;
  resize: vertical;
}

.ctitle:focus,
.cbody:focus {
  outline: none;
  border-color: #1a73e8;
}

.composer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint {
  font-size: 12px;
  color: #e5533d;
}

.publish {
  border: none;
  background: linear-gradient(135deg, #1a73e8, #4f9cf9);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  padding: 9px 26px;
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 3px 8px rgba(26, 115, 232, 0.3);
}

.publish:disabled {
  background: #c6d4e8;
  box-shadow: none;
  cursor: not-allowed;
}

/* 帖子列表 */
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.post {
  background: #fff;
  border: 1px solid #e4e9f0;
  border-radius: 14px;
  padding: 16px 18px;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.post:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(30, 60, 110, 0.1);
}

.post-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ptitle {
  font-size: 16px;
  color: #2c3e50;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.like-cell {
  font-size: 12.5px;
  color: #9aa5b1;
  white-space: nowrap;
}

.like-cell.mine {
  color: #e5533d;
  font-weight: 600;
}

.excerpt {
  margin-top: 6px;
  font-size: 13px;
  color: #5f6b7a;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.post-foot {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8a97a8;
}

.post-foot .author {
  color: #7a3ff2;
}

.post-foot .spacer {
  flex: 1;
}

.tip {
  text-align: center;
  color: #9aa5b1;
  padding: 50px 0;
  font-size: 14px;
}

.tip.err {
  color: #e5533d;
}

@media (max-width: 640px) {
  .community {
    padding: 0 12px 32px;
  }

  .nav {
    width: 100%;
    justify-content: center;
  }
}
</style>
