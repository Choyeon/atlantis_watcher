import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/liquid-glass.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.config.errorHandler = (err, instance, info) => {
  console.error('[Atlantis] 未捕获错误:', err, info)
}

app.mount('#app')

// 移除首屏骨架
const boot = document.getElementById('app-boot')
if (boot) boot.remove()
