import type { AlertSendStatus, HealthStatus } from "@/lib/types"

const currencyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  maximumFractionDigits: 2,
})

const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
})

export function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-"
  }

  return currencyFormatter.format(value)
}

export function formatDateTime(value: number | null | undefined) {
  if (!value) {
    return "-"
  }

  return dateTimeFormatter.format(new Date(value))
}

export function formatShortTime(value: number | null | undefined) {
  if (!value) {
    return "-"
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value))
}

export function formatAccountIdentity(accountName: string | null, accountId: string | null) {
  if (accountName && accountId) {
    return `${accountName} / ${accountId}`
  }

  return accountName || accountId || "Unknown account"
}

export function compactText(value: string | null | undefined, limit = 90) {
  if (!value) {
    return "-"
  }

  const normalized = value.replace(/\s+/g, " ").trim()
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit - 1)}…`
}

export function getHealthLabel(status: HealthStatus) {
  return {
    green: "Healthy",
    yellow: "Observe",
    red: "Risk",
  }[status]
}

export function getSendStatusLabel(status: AlertSendStatus) {
  return {
    sent: "Sent",
    failed: "Failed",
    skipped: "Skipped",
  }[status]
}

export function getSeverityLabel(value: string | null | undefined) {
  const raw = (value || "").toLowerCase()
  return {
    low: "Low",
    medium: "Medium",
    high: "High",
  }[raw] || (value || "-")
}

export function getCaptureStatusLabel(value: string | null | undefined) {
  const raw = (value || "").toLowerCase()
  return {
    ok: "OK",
    success: "Success",
    warning: "Warning",
    failed: "Failed",
    error: "Error",
  }[raw] || (value || "-")
}
