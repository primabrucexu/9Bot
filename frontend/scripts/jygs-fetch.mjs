import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..', '..')
const DEFAULT_STORAGE_STATE = path.join(repoRoot, 'data', 'jygs', 'auth', 'storage-state.json')
const DEFAULT_OUTPUT_DIR = path.join(repoRoot, 'data', 'jygs', 'diagrams')
const DIAGRAM_API_URL = 'https://app.jiuyangongshe.com/jystock-app/api/v1/action/diagram-url'

function parseArgs(argv) {
  const args = { date: [] }

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index]
    if (!token.startsWith('--')) {
      continue
    }

    const key = token.slice(2)
    const next = argv[index + 1]

    if (key === 'date') {
      if (!next || next.startsWith('--')) {
        throw new Error('--date 需要传入 YYYY-MM-DD')
      }
      args.date.push(next)
      index += 1
      continue
    }

    if (!next || next.startsWith('--')) {
      args[key] = true
      continue
    }

    args[key] = next
    index += 1
  }

  return args
}

function normalizeHeaders(headers) {
  return {
    accept: headers.accept ?? 'application/json, text/plain, */*',
    'content-type': headers['content-type'] ?? 'application/json',
    platform: headers.platform ?? '3',
    referer: headers.referer ?? 'https://www.jiuyangongshe.com/',
    token: headers.token ?? '',
  }
}

function extractImageUrl(value) {
  if (!value) {
    return null
  }

  if (typeof value === 'string') {
    return /^https?:\/\//i.test(value) ? value : null
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const candidate = extractImageUrl(item)
      if (candidate) {
        return candidate
      }
    }
    return null
  }

  if (typeof value === 'object') {
    for (const nestedValue of Object.values(value)) {
      const candidate = extractImageUrl(nestedValue)
      if (candidate) {
        return candidate
      }
    }
  }

  return null
}

function resolveExtension(imageUrl, contentType) {
  const pathname = new URL(imageUrl).pathname.toLowerCase()
  const matched = pathname.match(/\.(png|jpg|jpeg|webp)$/)
  if (matched) {
    return matched[0]
  }

  if (contentType?.includes('jpeg')) {
    return '.jpg'
  }
  if (contentType?.includes('webp')) {
    return '.webp'
  }
  return '.png'
}

async function ensureDirectory(dirPath) {
  await fs.mkdir(dirPath, { recursive: true })
}

async function loadDiagramViaPage(page, date) {
  const responsePromise = page.waitForResponse(
    (response) => response.url() === DIAGRAM_API_URL && response.request().method() === 'POST',
    { timeout: 120_000 },
  )
  await page.goto(`https://www.jiuyangongshe.com/action/${date}`, {
    waitUntil: 'domcontentloaded',
    timeout: 120_000,
  })
  const response = await responsePromise
  const payload = await response.json()
  return {
    payload,
    headers: normalizeHeaders(response.request().headers()),
  }
}

async function loadDiagramViaApi(requestContext, date, baseHeaders) {
  const response = await requestContext.post(DIAGRAM_API_URL, {
    data: { date },
    headers: {
      ...baseHeaders,
      timestamp: String(Date.now()),
    },
    timeout: 120_000,
  })
  const payload = await response.json()
  return { payload, headers: baseHeaders }
}

function validatePayload(payload, date) {
  if (payload?.errCode && payload.errCode !== '0') {
    if (String(payload.msg).includes('登录失效')) {
      throw new Error(`抓取 ${date} 失败：登录态已失效，请重新运行登录命令。`)
    }
    throw new Error(`抓取 ${date} 失败：${payload.msg || payload.errCode}`)
  }

  const imageUrl = extractImageUrl(payload?.data)
  if (!imageUrl) {
    throw new Error(`抓取 ${date} 失败：未从接口响应中解析到简图地址。`)
  }

  return imageUrl
}

async function downloadDiagram(requestContext, imageUrl, outputDir, date) {
  const response = await requestContext.get(imageUrl, { timeout: 120_000 })
  if (!response.ok()) {
    throw new Error(`下载 ${date} 图片失败：HTTP ${response.status()}`)
  }

  const extension = resolveExtension(imageUrl, response.headers()['content-type'])
  const outputPath = path.join(outputDir, `${date}${extension}`)
  await fs.writeFile(outputPath, await response.body())
  return outputPath
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const dates = args.date
  if (dates.length === 0) {
    throw new Error('至少需要传入一个 --date YYYY-MM-DD')
  }

  const storageStatePath = path.resolve(args['storage-state'] ?? DEFAULT_STORAGE_STATE)
  const outputDir = path.resolve(args['output-dir'] ?? DEFAULT_OUTPUT_DIR)
  const intervalMs = Number(args['interval-ms'] ?? '1000')
  if (!Number.isFinite(intervalMs) || intervalMs < 0) {
    throw new Error('--interval-ms 必须是非负整数')
  }

  await fs.access(storageStatePath)
  await ensureDirectory(outputDir)

  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  })

  const context = await browser.newContext({ storageState: storageStatePath })
  const page = await context.newPage()

  const results = []
  let baseHeaders = null

  try {
    for (let index = 0; index < dates.length; index += 1) {
      const date = dates[index]
      const { payload, headers } = baseHeaders
        ? await loadDiagramViaApi(context.request, date, baseHeaders)
        : await loadDiagramViaPage(page, date)

      if (!baseHeaders && headers.token) {
        baseHeaders = headers
      }

      const imageUrl = validatePayload(payload, date)
      const outputPath = await downloadDiagram(context.request, imageUrl, outputDir, date)
      results.push({
        date,
        outputPath,
        imageUrl,
        status: 'downloaded',
      })

      if (index < dates.length - 1 && intervalMs > 0) {
        await page.waitForTimeout(intervalMs)
      }
    }
  } finally {
    await browser.close()
  }

  process.stdout.write(`${JSON.stringify({ results }, null, 2)}\n`)
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = 1
})
