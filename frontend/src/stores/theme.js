import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'atlantis-theme'

/**
 * 主题 Store
 * 深色 / 浅色双主题，持久化到 localStorage，
 * 并同步 <html data-theme>，供 CSS 变量切换。
 */
export const useThemeStore = defineStore('theme', () => {
  const theme = ref(readInitial())

  function readInitial() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved === 'dark' || saved === 'light') return saved
    } catch {
      /* localStorage 不可用时降级 */
    }
    return 'dark'
  }

  function apply(value) {
    document.documentElement.setAttribute('data-theme', value)
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', value === 'dark' ? '#0b1220' : '#f4f6f8')
  }

  function setTheme(value) {
    theme.value = value === 'light' ? 'light' : 'dark'
  }

  function toggle() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  watch(
    theme,
    value => {
      apply(value)
      try {
        localStorage.setItem(STORAGE_KEY, value)
      } catch {
        /* 忽略写入失败 */
      }
    },
    { immediate: true }
  )

  return { theme, setTheme, toggle }
})
