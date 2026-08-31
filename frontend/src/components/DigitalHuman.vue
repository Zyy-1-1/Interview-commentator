<template>
  <div class="dh" :class="[style, { speaking }]">
    <svg viewBox="0 0 120 120" width="86" height="86" aria-hidden="true">
      <!-- 肩部/西装 -->
      <path d="M12 120 C12 92, 34 82, 60 82 C86  82, 108 92, 108 120 Z" :fill="c.suit" />
      <path d="M50 84 L60 100 L70 84 L60 90 Z" fill="#fff" />
      <!-- 领带/丝巾 -->
      <path v-if="style !== 'friendly'" d="M60 92 L56 104 L60 116 L64 104 Z" :fill="c.accent" />
      <circle v-else cx="60" cy="96" r="3" :fill="c.accent" />
      <!-- 头 -->
      <ellipse cx="60" cy="48" rx="24" ry="26" fill="#f6d7b8" />
      <!-- 耳朵 -->
      <circle cx="36" cy="50" r="4" fill="#f6d7b8" />
      <circle cx="84" cy="50" r="4" fill="#f6d7b8" />
      <!-- 头发 -->
      <path v-if="style === 'pro'" d="M36 44 C36 22, 84 22, 84 44 L84 36 C84 18, 36 18, 36 36 Z" :fill="c.hair" />
      <path v-if="style === 'pro'" d="M40 30 C50 22, 70 22, 80 30" :stroke="c.hair" stroke-width="9" fill="none" stroke-linecap="round" />
      <!-- friendly 长发包脸两侧 -->
      <path v-if="style === 'friendly'" d="M34 52 C30 20, 90 20, 86 52 C86 34, 74 26, 60 26 C46 26, 34 34, 34 52 Z" :fill="c.hair" />
      <rect v-if="style === 'friendly'" x="31" y="44" width="8" height="34" rx="4" :fill="c.hair" />
      <rect v-if="style === 'friendly'" x="81" y="44" width="8" height="34" rx="4" :fill="c.hair" />
      <!-- pressure 后梳油头 -->
      <path v-if="style === 'pressure'" d="M37 40 C37 20, 83 20, 83 40 L79 33 C70 25, 50 25, 41 33 Z" :fill="c.hair" />
      <!-- 眉 -->
      <path d="M46 41 L56 40" :stroke="c.hair" stroke-width="2.4" stroke-linecap="round" />
      <path d="M64 40 L74 41" :stroke="c.hair" stroke-width="2.4" stroke-linecap="round" />
      <!-- 眼镜(技术官/压力面) -->
      <template v-if="style !== 'friendly'">
        <circle cx="51" cy="48" r="7" fill="none" :stroke="c.glasses" stroke-width="2" />
        <circle cx="69" cy="48" r="7" fill="none" :stroke="c.glasses" stroke-width="2" />
        <path d="M58 48 L62 48" :stroke="c.glasses" stroke-width="2" />
      </template>
      <!-- 眼睛(眨眼动画) -->
      <g class="dh-eyes">
        <circle cx="51" :cy="style === 'pressure' ? 47 : 48" r="2.6" fill="#33404f" />
        <circle cx="69" :cy="style === 'pressure' ? 47 : 48" r="2.6" fill="#33404f" />
      </g>
      <!-- 鼻 -->
      <path d="M60 52 L59 58 L62 58" stroke="#e0b493" stroke-width="1.6" fill="none" stroke-linecap="round" />
      <!-- 嘴(说话时开合) -->
      <ellipse class="dh-mouth" cx="60" cy="66" rx="6.5" ry="1.8" fill="#b96a55" />
      <!-- 腮红(亲和) -->
      <template v-if="style === 'friendly'">
        <circle cx="45" cy="58" r="3.5" fill="#f5b7a3" opacity="0.55" />
        <circle cx="75" cy="58" r="3.5" fill="#f5b7a3" opacity="0.55" />
      </template>
    </svg>
  </div>
</template>

<script>
const COLORS = {
  pro: { suit: '#274466', hair: '#3a3f4a', accent: '#4f9cf9', glasses: '#2c3e50' },
  friendly: { suit: '#7a5a3e', hair: '#5b3a24', accent: '#f0a35e', glasses: '#8a6a4a' },
  pressure: { suit: '#3d3d45', hair: '#22252b', accent: '#e5533d', glasses: '#22252b' },
}

export default {
  name: 'DigitalHuman',
  props: {
    // pro | friendly | pressure
    style: { type: String, default: 'pro' },
    speaking: { type: Boolean, default: false },
  },
  computed: {
    c() {
      return COLORS[this.style] || COLORS.pro
    },
  },
}
</script>

<!-- 非 scoped:动画目标类带 dh- 前缀,避免污染 -->
<style>
.dh {
  display: inline-flex;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 32%, #eef4fd 0%, #dbe7f7 70%);
  padding: 6px;
  box-shadow: 0 4px 14px rgba(30, 60, 110, 0.14);
  animation: dhFloat 4.5s ease-in-out infinite;
}

.dh svg {
  display: block;
  border-radius: 50%;
  overflow: hidden;
}

@keyframes dhFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

/* 眨眼 */
.dh-eyes {
  transform-origin: 60px 48px;
  animation: dhBlink 5s infinite;
}

@keyframes dhBlink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.08); }
}

/* 说话:嘴部开合 */
.dh-mouth {
  transform-origin: 60px 66px;
  transition: ry 0.1s;
}

.dh.speaking .dh-mouth {
  animation: dhTalk 0.42s ease-in-out infinite;
}

@keyframes dhTalk {
  0%, 100% { transform: scaleY(1); }
  50% { transform: scaleY(2.6); }
}
</style>
