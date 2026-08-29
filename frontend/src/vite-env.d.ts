/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_MAIL_UI_URL?: string
  readonly VITE_REDIS_INSIGHT_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
