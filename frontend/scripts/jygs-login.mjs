import fs from 'node:fs/promises'
import path from 'node:path'
import readline from 'node:readline/promises'
import { fileURLToPath } from 'node:url'
import { stdin as input, stdout as output } from 'node:process'
import { chromium } from '@playwright/test'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')
const SIGNAL_POLL_INTERVAL_MS = 500

function parseArgs(argv) {
  const args = {}
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index]
    if (!token.startsWith('--')) {
      continue
    }

    const key = token.slice(2)
    const next = argv[index + 1]
    if (!next || next.startsWith('--')) {
      args[key] = true
      continue
    }

    args[key] = next
    index += 1
  }
  return args
}

function formatToday() {
  return new Date().toISOString().slice(0, 10)
}

function nowIso() {
  return new Date().toISOString()
}

async function ensureParentDirectory(filePath) {
  await fs.mkdir(path.dirname(filePath), { recursive: true })
}

async function writeStatus(statusFilePath, payload) {
  if (!statusFilePath) {
    return
  }

  await ensureParentDirectory(statusFilePath)
  await fs.writeFile(
    statusFilePath,
    JSON.stringify({ ...payload, updated_at: nowIso() }, null, 2),
    'utf-8',
  )
}

async function waitForSignal(signalFilePath) {
  if (!signalFilePath) {
    return false
  }

  while (true) {
    try {
      await fs.access(signalFilePath)
      return true
    } catch {
      await new Promise((resolve) => setTimeout(resolve, SIGNAL_POLL_INTERVAL_MS))
    }
  }
}

async function removeIfExists(filePath) {
  if (!filePath) {
    return
  }

  try {
    await fs.unlink(filePath)
  } catch (error) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'ENOENT') {
      return
    }
    throw error
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const storageStatePath = path.resolve(
    args['storage-state'] ?? path.join(repoRoot, 'data', 'jygs', 'auth', 'storage-state.json'),
  )
  const loginUrl = args.url ?? `https://www.jiuyangongshe.com/action/${formatToday()}`
  const signalFilePath = args['signal-file'] ? path.resolve(args['signal-file']) : null
  const statusFilePath = args['status-file'] ? path.resolve(args['status-file']) : null

  await ensureParentDirectory(storageStatePath)
  if (signalFilePath) {
    await ensureParentDirectory(signalFilePath)
    await removeIfExists(signalFilePath)
  }

  const browser = await chromium.launch({
    channel: 'msedge',
    headless: false,
  })

  const context = await browser.newContext()
  const page = await context.newPage()

  try {
    await page.goto(loginUrl, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await writeStatus(statusFilePath, {
      status: 'waiting',
      message: '请在打开的 Edge 窗口中完成登录，然后回到 9Bot 页面点击“我已登录，保存登录态”。',
      login_url: loginUrl,
    })

    if (signalFilePath) {
      await waitForSignal(signalFilePath)
    } else {
      console.log(`已打开登录页面：${loginUrl}`)
      console.log('请在 Edge 中完成登录，确认页面可正常访问后回到终端按回车。')
      const rl = readline.createInterface({ input, output })
      try {
        await rl.question('登录完成后按回车保存登录态：')
      } finally {
        rl.close()
      }
    }

    await writeStatus(statusFilePath, {
      status: 'saving',
      message: '正在保存登录态，请稍候。',
      login_url: loginUrl,
    })
    await context.storageState({ path: storageStatePath })
    await writeStatus(statusFilePath, {
      status: 'saved',
      message: `登录态已保存到：${storageStatePath}`,
      login_url: loginUrl,
    })

    if (!signalFilePath) {
      console.log(`登录态已保存到：${storageStatePath}`)
    }
  } catch (error) {
    await writeStatus(statusFilePath, {
      status: 'failed',
      message: error instanceof Error ? error.message : String(error),
      login_url: loginUrl,
    })
    throw error
  } finally {
    await removeIfExists(signalFilePath)
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = 1
})
