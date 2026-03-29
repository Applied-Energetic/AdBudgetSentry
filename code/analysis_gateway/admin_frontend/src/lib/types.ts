export type ThemeMode = "system" | "light" | "dark"

export type HealthStatus = "green" | "yellow" | "red"
export type AlertSendStatus = "sent" | "failed" | "skipped"

export interface AdminSummary {
  total_instances: number
  green_instances: number
  yellow_instances: number
  red_instances: number
  latest_capture_at: number | null
  latest_heartbeat_at: number | null
  total_analyses: number
  total_alerts: number
  latest_alert_at: number | null
}

export interface AdminInstanceSummary {
  instance_id: string
  alias: string | null
  remarks: string | null
  account_id: string | null
  account_name: string | null
  page_type: string | null
  page_url: string | null
  script_version: string | null
  health_status: HealthStatus
  last_seen_at: number | null
  last_heartbeat_at: number | null
  last_capture_at: number | null
  last_capture_status: string | null
  last_error: string | null
  consecutive_error_count: number
  last_row_count: number | null
  last_analysis_at: number | null
  last_analysis_summary: string | null
  last_analysis_provider: string | null
  last_analysis_model: string | null
  last_anomaly_type: string | null
  last_anomaly_severity: string | null
}

export interface AdminAlertRecord {
  id: number
  instance_id: string
  account_id: string | null
  account_name: string | null
  page_type: string | null
  page_url: string | null
  script_version: string | null
  alert_kind: string
  title: string
  content_preview: string | null
  channel: string | null
  channel_option: string | null
  delivery_provider: string
  send_status: AlertSendStatus
  provider_response: string | null
  severity: string | null
  anomaly_type: string | null
  triggered_at: number
  created_at: number
}

export interface AdminCaptureHistoryPoint {
  captured_at: number
  current_spend: number
  increase_amount: number
  baseline_spend: number | null
  compare_interval_min: number | null
  notify_threshold: number | null
  row_count: number | null
}

export interface AdminErrorRecord {
  id: number
  error_type: string
  error_message: string
  occurred_at: number
  page_url: string | null
  script_version: string | null
}

export interface AdminAnalysisRecord {
  id: number
  provider: string
  model: string
  anomaly_type: string
  severity: string
  score: number
  summary: string
  raw_text: string
  created_at: number
}

export interface AdminInstanceDetail extends AdminInstanceSummary {
  latest_current_spend: number | null
  latest_increase_amount: number | null
  recent_errors: AdminErrorRecord[]
  recent_alerts: AdminAlertRecord[]
  recent_analyses: AdminAnalysisRecord[]
  capture_history: AdminCaptureHistoryPoint[]
}

export interface DashboardPayload {
  summary: AdminSummary
  instances: AdminInstanceSummary[]
  alerts: AdminAlertRecord[]
}

export interface AlertsFilters {
  accountKeyword: string
  sendStatus: "" | AlertSendStatus
  alertKind: string
  dateFrom: string
  dateTo: string
}
