export const appConfig = {
  name: import.meta.env.VITE_APP_NAME || "Template Admin",
  apiUrl: (import.meta.env.VITE_API_URL || "").replace(/\/$/, ""),
  authMode: import.meta.env.VITE_AUTH_MODE || "session",
  defaultLocale: import.meta.env.VITE_DEFAULT_LOCALE || "zh-CN",
} as const;

if (import.meta.env.PROD && appConfig.authMode === "demo") {
  throw new Error("VITE_AUTH_MODE=demo is forbidden in production builds");
}
