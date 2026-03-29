import type {
  AdminAlertRecord,
  AdminCaptureHistoryPoint,
  AdminInstanceDetail,
  AdminInstanceSummary,
  AdminSummary,
  AlertsFilters,
  DashboardPayload,
} from "@/lib/types"

const API_BASE_URL = (import.meta.env.VITE_ADMIN_API_BASE_URL ?? "").replace(/\/$/, "")

function buildUrl(path: string) {
  return `${API_BASE_URL}${path}`
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }

  return (await response.json()) as T
}

function buildAlertsQuery(filters: Partial<AlertsFilters> = {}, limit = 500) {
  const params = new URLSearchParams()

  params.set("limit", String(limit))
  if (filters.accountKeyword) params.set("account_keyword", filters.accountKeyword)
  if (filters.sendStatus) params.set("send_status", filters.sendStatus)
  if (filters.alertKind) params.set("alert_kind", filters.alertKind)
  if (filters.dateFrom) params.set("date_from", filters.dateFrom)
  if (filters.dateTo) params.set("date_to", filters.dateTo)

  return params.toString()
}

export const adminApi = {
  async getDashboard(): Promise<DashboardPayload> {
    const [summary, instances, alerts] = await Promise.all([
      fetchJson<AdminSummary>("/admin/summary"),
      fetchJson<AdminInstanceSummary[]>("/admin/instances"),
      fetchJson<AdminAlertRecord[]>("/admin/api/alerts?limit=50"),
    ])

    return { summary, instances, alerts }
  },

  async getInstances(): Promise<AdminInstanceSummary[]> {
    return fetchJson<AdminInstanceSummary[]>("/admin/instances")
  },

  async getAlerts(filters: Partial<AlertsFilters> = {}, limit = 500): Promise<AdminAlertRecord[]> {
    const query = buildAlertsQuery(filters, limit)
    return fetchJson<AdminAlertRecord[]>(`/admin/api/alerts?${query}`)
  },

  async getInstanceDetail(instanceId: string): Promise<AdminInstanceDetail | null> {
    const response = await fetch(buildUrl(`/admin/api/instances/${encodeURIComponent(instanceId)}`), {
      headers: {
        Accept: "application/json",
      },
    })

    if (response.status === 404) {
      return null
    }

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`)
    }

    return (await response.json()) as AdminInstanceDetail
  },

  async getInstanceHistory(instanceId: string, limit = 500): Promise<AdminCaptureHistoryPoint[]> {
    return fetchJson<AdminCaptureHistoryPoint[]>(
      `/admin/api/instances/${encodeURIComponent(instanceId)}/history?limit=${Math.max(1, Math.min(limit, 500))}`,
    )
  },

  async updateInstanceMeta(instanceId: string, payload: { alias: string; remarks: string }) {
    return fetchJson(`/admin/api/instances/${encodeURIComponent(instanceId)}/meta`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })
  },

  async deleteInstance(instanceId: string) {
    return fetchJson(`/admin/api/instances/${encodeURIComponent(instanceId)}`, {
      method: "DELETE",
    })
  },

  buildAlertsExportHref(filters: Partial<AlertsFilters> = {}) {
    const query = buildAlertsQuery(filters, 5000)
    return buildUrl(`/admin/alerts/export.csv?${query}`)
  },
}
