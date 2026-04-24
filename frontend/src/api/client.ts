const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL?.trim() || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

function buildApiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers ?? {})
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers,
  })

  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`

    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        message = payload.detail
      }
    } catch {
      // ignore JSON parsing errors and use the fallback message
    }

    throw new Error(message)
  }

  if (response.status === 204) {
    return null as T
  }

  return response.json() as Promise<T>
}
