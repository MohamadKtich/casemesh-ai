import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig(({ mode }) => {
  const env = loadEnv(
    mode,
    process.cwd(),
    "",
  )

  const apiTarget =
    env.VITE_DEV_API_PROXY_TARGET ||
    "https://casemesh-api-dev.lemonwater-0bb11448.uaenorth.azurecontainerapps.io"

  return {
    plugins: [
      react(),
    ],

    server: {
      host: "0.0.0.0",
      port: 3000,

      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          secure: true,

          rewrite: (path) =>
            path.replace(
              /^\/api/,
              "",
            ),
        },
      },
    },
  }
})