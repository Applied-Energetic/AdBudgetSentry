import { ArrowLeft, RefreshCcw, Save, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { AlertSeverityBadge, AlertStatusBadge } from "@/components/alert-badges"
import { HealthBadge } from "@/components/health-badge"
import { TrendChartCard, type TrendChartPoint } from "@/components/trend-chart-card"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { adminApi } from "@/lib/api"
import {
  compactText,
  formatAccountIdentity,
  formatAlertKind,
  formatCurrency,
  formatDateTime,
  formatDisplayName,
  formatMetricKey,
  formatShortTime,
  formatStrategyTemplate,
  getCaptureStatusLabel,
} from "@/lib/format"
import type {
  AdminCaptureHistoryPoint,
  AdminInstanceDetail,
  MetricRegistryItem,
  StrategyDefinition,
} from "@/lib/types"

const HISTORY_WINDOW_MS = 12 * 60 * 60 * 1000

export function InstanceDetailPage() {
  const navigate = useNavigate()
  const { instanceId = "" } = useParams()
  const [detail, setDetail] = useState<AdminInstanceDetail | null | undefined>(undefined)
  const [history, setHistory] = useState<AdminCaptureHistoryPoint[]>([])
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([])
  const [metrics, setMetrics] = useState<MetricRegistryItem[]>([])
  const [form, setForm] = useState({ alias: "", remarks: "" })
  const [bindingForm, setBindingForm] = useState({ strategyId: "", enabled: "true", priority: "100" })
  const [saving, setSaving] = useState(false)
  const [bindingSaving, setBindingSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      const [detailResult, historyResult, strategyData, metricData] = await Promise.all([
        adminApi.getInstanceDetail(instanceId),
        adminApi.getInstanceHistory(instanceId, 500).catch(() => []),
        adminApi.getStrategies(),
        adminApi.getMetrics(),
      ])
      setDetail(detailResult)
      setHistory(historyResult)
      setStrategies(strategyData)
      setMetrics(metricData)
      if (detailResult) {
        setForm({
          alias: detailResult.alias || "",
          remarks: detailResult.remarks || "",
        })
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载实例详情失败")
    }
  }

  useEffect(() => {
    void load()
  }, [instanceId])

  const historyPoints = useMemo(() => {
    const threshold = Date.now() - HISTORY_WINDOW_MS
    return [...history]
      .sort((left, right) => left.captured_at - right.captured_at)
      .filter((item) => item.captured_at >= threshold)
  }, [history])

  const currentSpendChartData = useMemo<TrendChartPoint[]>(
    () =>
      historyPoints.map((item) => ({
        timestamp: item.captured_at,
        label: formatShortTime(item.captured_at),
        value: item.current_spend,
      })),
    [historyPoints],
  )

  const strategyReadyMetrics = useMemo(
    () => metrics.filter((item) => item.is_enabled && item.is_strategy_ready),
    [metrics],
  )

  const availableStrategies = useMemo(
    () =>
      strategies.filter(
        (strategy) => !detail?.strategy_bindings.some((binding) => binding.strategy_id === strategy.id) && strategy.enabled,
      ),
    [detail?.strategy_bindings, strategies],
  )

  const saveMeta = async () => {
    try {
      setSaving(true)
      setError(null)
      await adminApi.updateInstanceMeta(instanceId, form)
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存实例信息失败")
    } finally {
      setSaving(false)
    }
  }

  const saveBinding = async () => {
    if (!bindingForm.strategyId) return

    try {
      setBindingSaving(true)
      setError(null)
      await adminApi.saveInstanceStrategyBinding(instanceId, {
        strategy_id: Number(bindingForm.strategyId),
        enabled: bindingForm.enabled === "true",
        priority: Number(bindingForm.priority) || 100,
      })
      setBindingForm({ strategyId: "", enabled: "true", priority: "100" })
      await load()
    } catch (bindingError) {
      setError(bindingError instanceof Error ? bindingError.message : "保存策略绑定失败")
    } finally {
      setBindingSaving(false)
    }
  }

  const removeBinding = async (strategyId: number) => {
    try {
      setError(null)
      await adminApi.deleteInstanceStrategyBinding(instanceId, strategyId)
      await load()
    } catch (bindingError) {
      setError(bindingError instanceof Error ? bindingError.message : "删除策略绑定失败")
    }
  }

  const deleteInstance = async () => {
    if (!window.confirm("删除后将移除当前实例的采集、策略命中和告警记录，是否继续？")) return

    try {
      setDeleting(true)
      await adminApi.deleteInstance(instanceId)
      navigate("/admin")
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "删除实例失败")
    } finally {
      setDeleting(false)
    }
  }

  if (detail === undefined && !error) {
    return <div className="page-subheading">正在加载实例详情...</div>
  }

  if (detail === null) {
    return (
      <Card className="soft-panel max-w-xl">
        <CardHeader>
          <CardTitle>实例不存在</CardTitle>
          <CardDescription>当前实例 ID 无法匹配到有效记录，可能已经被删除。</CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/admin" className={buttonVariants({ variant: "outline" })}>
            <ArrowLeft className="size-4" />
            返回总览
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (!detail) {
    return (
      <Card className="soft-panel max-w-xl">
        <CardHeader>
          <CardTitle>实例详情加载失败</CardTitle>
          <CardDescription>{error || "请稍后重试。"}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void load()}>重新加载</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-3">
          <Link to="/admin" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="size-4" />
            返回总览
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="page-heading">{detail.alias || formatDisplayName(detail.account_name, detail.account_id)}</h1>
            <HealthBadge status={detail.health_status} />
          </div>
          <p className="page-subheading">{formatAccountIdentity(detail.account_name, detail.account_id)}</p>
        </div>

        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCcw className="size-4" />
            刷新
          </Button>
          <Button variant="destructive" onClick={() => void deleteInstance()} disabled={deleting}>
            <Trash2 className="size-4" />
            {deleting ? "删除中..." : "删除实例"}
          </Button>
        </div>
      </div>

      {error ? <div className="text-sm text-rose-600 dark:text-rose-300">{error}</div> : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricValueCard title="最新总花费" value={formatCurrency(detail.latest_current_spend)} />
        <MetricValueCard title="最近采集时间" value={formatDateTime(detail.last_capture_at)} />
        <MetricValueCard title="最近心跳" value={formatDateTime(detail.last_heartbeat_at)} />
        <MetricValueCard title="采集状态" value={getCaptureStatusLabel(detail.last_capture_status)} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>实例信息</CardTitle>
            <CardDescription>维护实例别名和备注，便于在策略页和告警页快速识别。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="instance-alias">
                实例别名
              </label>
              <Input
                id="instance-alias"
                value={form.alias}
                onChange={(event) => setForm((current) => ({ ...current, alias: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="instance-remarks">
                备注
              </label>
              <Textarea
                id="instance-remarks"
                value={form.remarks}
                onChange={(event) => setForm((current) => ({ ...current, remarks: event.target.value }))}
              />
            </div>
            <Button onClick={() => void saveMeta()} disabled={saving}>
              <Save className="size-4" />
              {saving ? "保存中..." : "保存实例信息"}
            </Button>
          </CardContent>
        </Card>

        <section className="info-grid">
          <InfoItem label="实例 ID" value={detail.instance_id} />
          <InfoItem label="页面类型" value={detail.page_type || "-"} />
          <InfoItem label="脚本版本" value={detail.script_version || "-"} />
          <InfoItem label="最近错误" value={compactText(detail.last_error, 80)} />
          <InfoItem label="最近分析" value={compactText(detail.last_analysis_summary, 80)} />
          <InfoItem label="最近行数" value={String(detail.last_row_count ?? "-")} />
          <InfoItem label="最近分析类型" value={detail.last_anomaly_type || "-"} />
          <InfoItem label="最近分析级别" value={detail.last_anomaly_severity || "-"} />
        </section>
      </section>

      <TrendChartCard
        title="总花费趋势"
        description="聚焦最近 12 小时的总花费采样，用于观察实例整体波动。"
        data={currentSpendChartData}
        color="var(--color-chart-1)"
        emptyText="最近 12 小时内采样点不足，暂时无法绘制总花费趋势。"
        valueLabel="元"
      />

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>策略绑定</CardTitle>
            <CardDescription>按实例绑定或解绑策略。阶段一只有 `花费` 指标可执行。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">选择策略</label>
                <Select
                  value={bindingForm.strategyId || "none"}
                  onValueChange={(value) =>
                    setBindingForm((current) => ({ ...current, strategyId: value === "none" ? "" : String(value ?? "") }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="请选择策略" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">请选择策略</SelectItem>
                    {availableStrategies.map((strategy) => (
                      <SelectItem key={strategy.id} value={String(strategy.id)}>
                        {strategy.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">启用状态</label>
                <Select
                  value={bindingForm.enabled}
                  onValueChange={(value) => setBindingForm((current) => ({ ...current, enabled: String(value ?? "true") }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">启用</SelectItem>
                    <SelectItem value="false">停用</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">优先级</label>
                <Input
                  type="number"
                  value={bindingForm.priority}
                  onChange={(event) => setBindingForm((current) => ({ ...current, priority: event.target.value }))}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">可执行指标</label>
                <div className="rounded-2xl border border-border/70 bg-background/80 px-4 py-3 text-sm text-muted-foreground">
                  {strategyReadyMetrics.map((item) => item.display_name).join(" / ") || "暂无"}
                </div>
              </div>
            </div>

            <Button onClick={() => void saveBinding()} disabled={bindingSaving || !bindingForm.strategyId}>
              {bindingSaving ? "保存中..." : "添加绑定"}
            </Button>

            <div className="space-y-3">
              {detail.strategy_bindings.map((binding) => (
                <div key={binding.id} className="record-card">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{binding.strategy_name}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {formatStrategyTemplate(binding.template_type)} / {formatMetricKey(binding.target_metric)}
                      </div>
                    </div>
                    <Button variant="destructive" size="sm" onClick={() => void removeBinding(binding.strategy_id)}>
                      删除绑定
                    </Button>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                    <div>启用：{binding.enabled ? "是" : "否"}</div>
                    <div>优先级：{binding.priority}</div>
                    <div>窗口：{String(binding.params.window_minutes ?? "-")} 分钟</div>
                    <div>指标：{formatMetricKey(binding.target_metric)}</div>
                  </div>
                </div>
              ))}
              {detail.strategy_bindings.length === 0 ? <div className="text-sm text-muted-foreground">当前实例尚未绑定策略。</div> : null}
            </div>
          </CardContent>
        </Card>

        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>最近策略命中</CardTitle>
            <CardDescription>查看最近由哪些策略触发，以及它们使用了什么证据。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.recent_strategy_hits.map((hit) => (
              <div key={hit.id} className="record-card">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-medium">{hit.strategy_name}</div>
                  <AlertSeverityBadge severity={hit.severity} />
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {formatStrategyTemplate(hit.template_type)} / {formatMetricKey(hit.target_metric)} / {formatDateTime(hit.triggered_at)}
                </div>
                <div className="mt-2 text-sm text-foreground">得分：{hit.score.toFixed(2)}</div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {hit.evidence.map((evidence) => (
                    <li key={evidence}>{evidence}</li>
                  ))}
                </ul>
                {hit.recommendation ? <div className="mt-2 text-sm text-foreground">建议：{hit.recommendation}</div> : null}
              </div>
            ))}
            {detail.recent_strategy_hits.length === 0 ? <div className="text-sm text-muted-foreground">最近没有策略命中记录。</div> : null}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>最近告警</CardTitle>
            <CardDescription>告警现在会带上触发策略链路，方便反查来源。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.recent_alerts.map((alert) => (
              <div key={alert.id} className="record-card">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-medium">{alert.title}</div>
                  <AlertStatusBadge status={alert.send_status} />
                  <AlertSeverityBadge severity={alert.severity} />
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {alert.strategy_name || formatAlertKind(alert.alert_kind)} / {formatDateTime(alert.triggered_at)}
                </div>
                <div className="mt-2 text-sm leading-6 text-foreground">{compactText(alert.content_preview, 160)}</div>
              </div>
            ))}
            {detail.recent_alerts.length === 0 ? <div className="text-sm text-muted-foreground">暂无告警记录。</div> : null}
          </CardContent>
        </Card>

        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>最近错误</CardTitle>
            <CardDescription>保留实例错误排查入口，便于区分策略问题和采集问题。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.recent_errors.map((errorItem) => (
              <div key={errorItem.id} className="record-card">
                <div className="font-medium">{errorItem.error_type}</div>
                <div className="mt-1 text-sm text-muted-foreground">{formatDateTime(errorItem.occurred_at)}</div>
                <div className="mt-2 text-sm leading-6 text-foreground">{errorItem.error_message}</div>
              </div>
            ))}
            {detail.recent_errors.length === 0 ? <div className="text-sm text-muted-foreground">暂无错误记录。</div> : null}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

function MetricValueCard({ title, value }: { title: string; value: string }) {
  return (
    <Card className="soft-panel">
      <CardHeader className="pb-2">
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-3xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/80 px-4 py-4">
      <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-sm text-foreground">{value}</div>
    </div>
  )
}
