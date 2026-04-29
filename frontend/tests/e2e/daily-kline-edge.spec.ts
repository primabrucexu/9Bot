import { expect, test } from '@playwright/test'
import { registerMockApi } from './support/mockApi'

test('首页显示基础股票池并支持搜索', async ({ page }) => {
  await registerMockApi(page)

  await page.goto('/')

  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { name: 'A 股数据工作台' })).toBeVisible()
  await expect(page.getByText('上证指数')).toBeVisible()
  await expect(page.getByText('深证成指')).toBeVisible()
  await expect(page.getByText('创业板指')).toBeVisible()
  await expect(page.getByRole('cell', { name: '贵州茅台' })).toBeVisible()

  await page.getByLabel('搜索股票代码或名称').fill('平安')
  await page.getByRole('button', { name: '搜索' }).click()

  await expect(page.getByRole('cell', { name: '平安银行' })).toBeVisible()
  await expect(page.getByText('当前共 1 只')).toBeVisible()
})

test('首页可运行涨停复制选股并展示结果', async ({ page }) => {
  await registerMockApi(page)

  await page.goto('/')
  await page.getByRole('button', { name: '运行选股' }).click()

  await expect(page.getByRole('heading', { name: '涨停复制 Top10' })).toBeVisible()
  await expect(page.getByText('截止 2026-04-27')).toBeVisible()
  await expect(page.getByRole('row', { name: /600519 贵州茅台 白酒 86/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /002594 比亚迪 汽车整车 79/ })).toBeVisible()
})

test('选股接口失败时仅影响选股面板', async ({ page }) => {
  await registerMockApi(page, {
    limitUpCopyStatus: 500,
    limitUpCopyErrorDetail: '获取选股结果失败',
  })

  await page.goto('/')
  await page.getByRole('button', { name: '运行选股' }).click()

  await expect(page.getByRole('heading', { name: '选股失败' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '贵州茅台' })).toBeVisible()
})

test('首页搜索无结果时显示空状态', async ({ page }) => {
  await registerMockApi(page)

  await page.goto('/')
  await page.getByLabel('搜索股票代码或名称').fill('不存在')
  await page.getByRole('button', { name: '搜索' }).click()

  await expect(page.getByRole('heading', { name: '没有匹配结果' })).toBeVisible()
})

test('大盘接口失败时首页仍可展示股票池', async ({ page }) => {
  await registerMockApi(page, {
    marketOverviewStatus: 500,
    marketOverviewErrorDetail: '获取大盘数据失败',
  })

  await page.goto('/')

  await expect(page.getByRole('heading', { name: '大盘数据暂时不可用' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '贵州茅台' })).toBeVisible()

  await page.getByLabel('搜索股票代码或名称').fill('平安')
  await page.getByRole('button', { name: '搜索' }).click()
  await expect(page.getByRole('cell', { name: '平安银行' })).toBeVisible()
})

test('可从股票池进入详情页', async ({ page }) => {
  await registerMockApi(page)

  await page.goto('/')
  await page.getByRole('row', { name: /贵州茅台/ }).getByRole('button', { name: '查看详情' }).click()

  await expect(page).toHaveURL(/\/stocks\/600519$/)
  await expect(page.getByRole('heading', { name: /贵州茅台/ })).toBeVisible()
})

test('没有日线数据时显示市场同步提示', async ({ page }) => {
  await registerMockApi(page)

  await page.goto('/stocks/002594')

  await expect(page.getByRole('heading', { name: '还没有日线数据' })).toBeVisible()
  await expect(page.getByRole('button', { name: '立即同步近30天市场日线' })).toBeVisible()
})

test('可从个股页生成日报并跳转到日报页', async ({ page }) => {
  await registerMockApi(page)

  await page.goto('/stocks/600519')
  await page.getByRole('button', { name: '生成 AI 日报' }).click()

  await expect(page).toHaveURL(/\/reports\/2026-04-25$/)
  await expect(page.getByRole('heading', { name: '2026-04-25 市场观察日报' })).toBeVisible()
  await expect(page.getByText('贵州茅台维持多头结构')).toBeVisible()
})

test('韭研公社页面可完成网页登录并抓取最新简图', async ({ page }) => {
  await registerMockApi(page)

  await page.goto('/jygs')
  await expect(page.getByRole('heading', { name: '涨停简图工作台' })).toBeVisible()
  await expect(page.getByText('还没有可用登录态')).toBeVisible()

  await page.getByRole('button', { name: '启动登录' }).click()
  await expect(page.getByText('等待登录')).toBeVisible()
  await expect(
    page
      .locator('.status-banner')
      .getByText('请在打开的 Edge 窗口中完成登录，然后回到 9Bot 页面点击“我已登录，保存登录态”。'),
  ).toBeVisible()

  await page.getByRole('button', { name: '我已登录，保存登录态' }).click()
  await expect(page.getByText('登录态已保存，可以开始抓取最新涨停简图。')).toBeVisible()

  await page.getByRole('button', { name: '抓取最新简图' }).click()
  await expect(page.getByText('最新交易日涨停简图抓取完成。')).toBeVisible()
  await expect(page.getByRole('img', { name: '韭研公社 2026-04-29 涨停简图' })).toBeVisible()
})

test('韭研公社启动登录失败时显示错误提示', async ({ page }) => {
  await registerMockApi(page, {
    jygsLoginStartCode: 500,
    jygsLoginStartErrorDetail: '启动网页登录失败',
  })

  await page.goto('/jygs')
  await page.getByRole('button', { name: '启动登录' }).click()

  await expect(page.getByText('启动网页登录失败')).toBeVisible()
  await expect(page.getByText('还没有可用登录态')).toBeVisible()
})

test('韭研公社抓图失败时仅影响当前页面面板', async ({ page }) => {
  await registerMockApi(page, {
    jygsStatus: {
      login_ready: true,
      storage_state_path: 'D:/dev/9Bot/backend/data/jygs/auth/storage-state.json',
      login_flow: {
        status: 'saved',
        message: '登录态已保存。',
        login_url: 'https://www.jiuyangongshe.com/action/2026-04-29',
        updated_at: '2026-04-29T09:12:00+08:00',
      },
      latest: null,
    },
    jygsFetchCode: 500,
    jygsFetchErrorDetail: '抓取最新简图失败',
  })

  await page.goto('/jygs')
  await page.getByRole('button', { name: '抓取最新简图' }).click()

  await expect(page.getByText('抓取最新简图失败')).toBeVisible()
  await expect(page.getByText('还没有本地简图')).toBeVisible()
})
