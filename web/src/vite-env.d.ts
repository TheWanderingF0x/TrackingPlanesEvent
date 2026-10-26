/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USE_STATIC?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
