import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

function fixture(kind: 'signal-example' | 'no-signal-example' | 'invalid-example', file: string) {
  return fileURLToPath(new URL(`../../../demo/${kind}/${file}`, import.meta.url))
}

test('sample evidence, assessment, saved review, and CSV export work together', async ({ page }) => {
  const externalRequests: string[] = []
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (!['localhost', '127.0.0.1'].includes(url.hostname)) {
      externalRequests.push(url.href)
      return route.abort()
    }
    return route.continue()
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Understand the SOC behind/ })).toBeVisible()
  await page.getByRole('button', { name: 'Explore sample assessment' }).click()
  await expect(page).toHaveURL(/\/submissions\//)
  await expect(page.getByText('Synthetic example · No real operational data')).toBeVisible()
  await expect(page.locator('.result-card')).toHaveCount(3)
  await expect(page.locator('.result-card').first()).toContainText('of 6 evaluated')
  await page.getByRole('button', { name: 'View evidence' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Observation and source evidence' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText('CASE-01').first()).toBeVisible()
  await expect(dialog.getByText('CASE-02').first()).toBeVisible()
  await dialog.getByLabel('Decision').selectOption('needs_context')
  const note = `Review follow-up ${Date.now()}`
  await dialog.getByLabel('Review note').fill(note)
  await dialog.getByRole('button', { name: 'Save review' }).click()
  await expect(dialog.getByText('Review saved')).toBeVisible()
  await page.reload()
  await expect(dialog.getByLabel('Decision')).toHaveValue('needs_context')
  await expect(dialog.getByLabel('Review note')).toHaveValue(note)
  await dialog.getByRole('button', { name: 'Close evidence' }).click()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export CSV' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/^sat-sa-review-.*\.csv$/)
  const csv = await readFile(await download.path(), 'utf8')
  expect(csv).toContain('CASE-01')
  expect(csv).toContain('needs_context')
  expect(csv).toContain(note)
  expect(externalRequests).toEqual([])
})

test('custom CSVs import, assess, and reject invalid rows without a submission', async ({ page }) => {
  await page.goto('/submissions/new')
  const unique = Date.now().toString()
  await page.getByLabel('Entity name').fill(`Evaluation entity ${unique}`)
  await page.locator('#period-start').fill('2026-01-01')
  await page.locator('#period-end').fill('2026-01-08')
  await page.locator('#file-assets').setInputFiles(fixture('no-signal-example', 'assets.csv'))
  await page.locator('#file-alerts').setInputFiles(fixture('no-signal-example', 'alerts.csv'))
  await page.locator('#file-cases').setInputFiles(fixture('no-signal-example', 'cases.csv'))
  await page.locator('input[name="coverage"][value="complete"]').check()
  await page.getByRole('checkbox', { name: /I confirm/ }).check()
  await page.getByRole('button', { name: 'Import submission' }).click()
  await expect(page.getByText('Evidence validated and stored successfully.')).toBeVisible()
  await page.getByRole('button', { name: 'Run assessment' }).click()
  await expect(page.locator('.result-card')).toHaveCount(3)
  await expect(page.getByText('No signals in these checks')).toBeVisible()

  const totalBeforeInvalid = (await (await page.request.get('/api/v1/overview')).json()).submissions
  await page.goto('/submissions/new')
  await page.getByLabel('Entity name').fill(`Invalid evaluation ${unique}`)
  await page.locator('#period-start').fill('2026-01-01')
  await page.locator('#period-end').fill('2026-01-08')
  await page.locator('#file-assets').setInputFiles(fixture('invalid-example', 'assets.csv'))
  await page.locator('#file-alerts').setInputFiles(fixture('invalid-example', 'alerts.csv'))
  await page.locator('#file-cases').setInputFiles(fixture('invalid-example', 'cases.csv'))
  await page.getByRole('button', { name: 'Import submission' }).click()
  await expect(page.getByRole('alert').last()).toContainText('alerts.csv')
  await expect(page.getByRole('alert').last()).toContainText('cases.csv')
  await expect(page).toHaveURL(/\/submissions\/new/)
  const totalAfterInvalid = (await (await page.request.get('/api/v1/overview')).json()).submissions
  expect(totalAfterInvalid).toBe(totalBeforeInvalid)
})

test('mobile navigation and evidence drawer fit the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Open menu' }).click()
  await expect(page.getByRole('complementary', { name: 'Primary navigation' })).toBeVisible()
  await page.getByRole('button', { name: 'Close menu' }).first().click()
  await page.getByRole('button', { name: 'Explore sample assessment' }).click()
  await page.getByRole('button', { name: 'View evidence' }).first().click()
  await expect(page.getByRole('dialog', { name: 'Observation and source evidence' })).toBeVisible()
  const width = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(width).toBeLessThanOrEqual(375)
})

test('evidence review opens and closes from the keyboard with focus restored', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Explore sample assessment' }).click()
  const trigger = page.getByRole('button', { name: 'View evidence' }).first()
  await trigger.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog', { name: 'Observation and source evidence' })
  await expect(dialog).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(trigger).toBeFocused()
})

test('core screens have no automated WCAG A or AA violations', async ({ page }) => {
  function violationSummary(report: Awaited<ReturnType<AxeBuilder['analyze']>>) {
    return report.violations.flatMap(item => item.nodes.map(node => {
      const detail = node.any[0]?.data as { fgColor?: string; bgColor?: string } | undefined
      return `${item.id} ${node.target.join(' ')} ${detail?.fgColor ?? ''}/${detail?.bgColor ?? ''}`
    })).join('\n')
  }
  for (const path of ['/', '/submissions/new']) {
    await page.goto(path)
    const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    expect(report.violations.length, `${path}:\n${violationSummary(report)}`).toBe(0)
  }
  await page.goto('/')
  await page.getByRole('button', { name: 'Explore sample assessment' }).click()
  await page.getByRole('button', { name: 'View evidence' }).first().click()
  const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  expect(report.violations.length, `evidence:\n${violationSummary(report)}`).toBe(0)
})
