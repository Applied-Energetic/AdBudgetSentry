import type { AlertSendStatus, HealthStatus } from "@/lib/types"

const currencyFormatter = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  maximumFractionDigits: 2,
})

const decimalFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
})

function sanitizeIdentityPart(value: string | null | undefined) {
  if (!value) return ""
  const normalized = value.trim()
  if (!normalized) return ""

  const lower = normalized.toLowerCase()
  if (lower.includes("unknown") || normalized.includes("未识别") || normalized.includes("未知")) {
    return ""
  }

  return normalized
}

export function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-"
  }

  return currencyFormatter.format(value)
}

export function formatDecimal(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-"
  }

  return decimalFormatter.format(value)
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

export function formatDisplayName(accountName: string | null, accountId: string | null) {
  const cleanAccountName = sanitizeIdentityPart(accountName)
  const cleanAccountId = sanitizeIdentityPart(accountId)
  return cleanAccountName || cleanAccountId || "未命名实例"
}

export function formatAccountIdentity(accountName: string | null, accountId: string | null) {
  const cleanAccountName = sanitizeIdentityPart(accountName)
  const cleanAccountId = sanitizeIdentityPart(accountId)

  if (cleanAccountName && cleanAccountId && cleanAccountName !== cleanAccountId) {
    return `${cleanAccountName} / ${cleanAccountId}`
  }

  return cleanAccountName || cleanAccountId || "未知账户"
}

export function compactText(value: string | null | undefined, limit = 90) {
  if (!value) {
    return "-"
  }

  const normalized = value.replace(/\s+/g, " ").trim()
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit - 3)}...`
}

export function getHealthLabel(status: HealthStatus) {
  return {
    green: "健康",
    yellow: "关注",
    red: "风险",
  }[status]
}

export function getSendStatusLabel(status: AlertSendStatus) {
  return {
    sent: "已发送",
    failed: "发送失败",
    skipped: "已跳过",
  }[status]
}

export function getSeverityLabel(value: string | null | undefined) {
  const raw = (value || "").toLowerCase()
  return (
    {
      low: "低",
      medium: "中",
      high: "高",
    }[raw] || value || "-"
  )
}

export function getCaptureStatusLabel(value: string | null | undefined) {
  const raw = (value || "").toLowerCase()
  return (
    {
      ok: "正常",
      success: "成功",
      warning: "预警",
      failed: "失败",
      error: "错误",
    }[raw] || value || "-"
  )
}

export function formatAlertKind(value: string | null | undefined) {
  const raw = (value || "").toLowerCase()
  return (
    {
      threshold: "阈值告警",
      offline: "离线告警",
      anomaly: "异常告警",
      error: "错误告警",
      analysis: "分析告警",
      spend_jump: "消耗突增",
      spend_drop: "消耗骤降",
    }[raw] || value || "-"
  )
}
