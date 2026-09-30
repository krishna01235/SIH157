import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  webServer: process.env.CI ? [
    {
      command: '../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/ready',
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
    },
  ] : undefined,
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5173',
    ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}),
    trace: 'retain-on-failure',
  },
})
