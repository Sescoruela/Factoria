const {defineConfig} = require('playwright/test');
const path = require('node:path');
const python = process.env.FACTORIA_TEST_PYTHON || 'python';
const port = Number(process.env.FACTORIA_BROWSER_PORT || 8769);
const artifacts = path.resolve(process.env.FACTORIA_BROWSER_ARTIFACT_DIR || __dirname);

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: '*.spec.cjs',
  fullyParallel: false,
  workers: 1, // The two shells share the same disposable workspace preferences.
  forbidOnly: !!process.env.CI,
  retries: 0, // A flaky run must remain visible, not be hidden by a retry.
  timeout: 45000,
  globalTimeout: 300000,
  expect: {timeout: 10000},
  outputDir: path.join(artifacts, 'test-results'),
  reporter: [
    ['list'],
    ['html', {outputFolder: path.join(artifacts, 'playwright-report'), open: 'never'}],
    ['json', {outputFile: path.join(artifacts, 'results.json')}],
    ['junit', {outputFile: path.join(artifacts, 'results.xml')}],
  ],
  use: {
    browserName: 'chromium',
    baseURL: `http://127.0.0.1:${port}`,
    viewport: {width: 1440, height: 1000},
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: process.env.FACTORIA_CHROMIUM_EXECUTABLE ? {
      executablePath: process.env.FACTORIA_CHROMIUM_EXECUTABLE,
    } : {},
  },
  webServer: {
    command: `"${python}" fixture_server.py`,
    cwd: __dirname,
    url: `http://127.0.0.1:${port}/__test__/fixture`,
    reuseExistingServer: false,
    timeout: 20000,
  },
});
