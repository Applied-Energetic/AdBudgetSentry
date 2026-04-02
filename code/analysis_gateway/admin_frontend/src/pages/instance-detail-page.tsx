import { ArrowLeft, RefreshCcw, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { AlertSeverityBadge, AlertStatusBadge } from "@/components/alert-badges"
import { HealthBadge } from "@/components/health-badge"
import { TrendChartCard, type TrendChartPoint } from "@/components/trend-chart-card"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { adminApi } from "@/lib/api"
import {
  compactText,
  formatAccountIdentity,
  formatAlertKind,
  formatCurrency,
  formatDateTime,
  formatDisplayName,
  formatShortTime,
  getCaptureStatusLabel,
} from "@/lib/format"
import type { AdminCaptureHistoryPoint, AdminInstanceDetail } from "@/lib/types"

const HISTORY_WINDOW_MS = 12 * 60 * 60 * 1000

export function InstanceDetailPage() {
  const navigate = useNavigate()
  const { instanceId = "" } = useParams()
  const [detail, setDetail] = useState<AdminInstanceDetail | null | undefined>(undefined)
  const [history, setHistory] = useState<AdminCaptureHistoryPoint[]>([])
  const [form, setForm] = useState({ alias: "", remarks: "" })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      const [detailResult, historyResult] = await Promise.all([
        adminApi.getInstanceDetail(instanceId),
        adminApi.getInstanceHistory(instanceId, 500).catch(() => []),
      ])
      setDetail(detailResult)
      setHistory(historyResult)
      if (detailResult) {
        setForm({
          alias: detailResult.alias || "",
          remarks: detailResult.remarks || "",
        })
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败")
    }
  }

  useEffect(() => {
    void load()
  }, [instanceId])

  const historyPoints = useMemo(() => {
    const now = Date.now()
    const threshold = now - HISTORY_WINDOW_MS
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

  const increaseAmountChartData = useMemo<TrendChartPoint[]>(
    () =>
      historyPoints.map((item) => ({
        timestamp: item.captured_at,
        label: formatShortTime(item.captured_at),
        value: item.increase_amount,
        referenceValue: item.baseline_increase_amount ?? null,
      })),
    [historyPoints],
  )

  const windowMinutes = useMemo(() => {
    if (!detail) return 10
    const latestWithWindow = [...history]
      .sort((left, right) => right.captured_at - left.captured_at)
      .find((item) => item.compare_interval_min)
    return latestWithWindow?.compare_interval_min ?? 10
  }, [detail, history])

  const saveMeta = async () => {
    try {
      setSaving(true)
      await adminApi.updateInstanceMeta(instanceId, form)
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败")
    } finally {
      setSaving(false)
    }
  }

  const deleteInstance = async () => {
    const confirmed = window.confirm("删除实例后，如果脚本再次上报，这个实例会重新出现。确认继续吗？")
    if (!confirmed) return

    try {
      await adminApi.deleteInstance(instanceId)
      navigate("/admin")
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "删除失败")
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
          <CardDescription>请确认实例编号是否正确，或返回总览重新选择。</CardDescription>
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
          <CardTitle>实例加载失败</CardTitle>
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
          <Button variant="outline" onClick={() => void load()} className="w-full sm:w-auto">
            <RefreshCcw className="size-4" />
            刷新
          </Button>
          <Button variant="destructive" onClick={() => void deleteInstance()} className="w-full sm:w-auto">
            <Trash2 className="size-4" />
            删除实例
          </Button>
        </div>
      </div>

      {error ? <div className="text-sm text-rose-600 dark:text-rose-300">{error}</div> : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricValueCard title="当前总消耗" value={formatCurrency(detail.latest_current_spend)} />
        <MetricValueCard title={`${windowMinutes} 分钟窗口增量`} value={formatCurrency(detail.latest_increase_amount)} />
        <MetricValueCard title="最近采样" value={formatDateTime(detail.last_capture_at)} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>实例名称与备注</CardTitle>
            <CardDescription>这里修改的别名和备注只保存在后台监控系统中，不会同步到油猴脚本。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="instance-alias">
                实例名称
              </label>
              <Input
                id="instance-alias"
                value={form.alias}
                onChange={(event) => setForm((current) => ({ ...current, alias: event.target.value }))}
                placeholder="例如：投流主账号 01"
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
                placeholder="填写负责人、用途、风险说明或其他补充信息"
              />
            </div>
            <Button onClick={() => void saveMeta()} disabled={saving}>
              {saving ? "保存中..." : "保存名称与备注"}
            </Button>
          </CardContent>
        </Card>

        <section className="info-grid">
          <InfoItem label="实例 ID" value={detail.instance_id} />
          <InfoItem label="页面类型" value={detail.page_type || "-"} />
          <InfoItem label="脚本版本" value={detail.script_version || "-"} />
          <InfoItem label="采样状态" value={getCaptureStatusLabel(detail.last_capture_status)} />
          <InfoItem label="最近心跳" value={formatDateTime(detail.last_heartbeat_at)} />
          <InfoItem label="最近错误" value={compactText(detail.last_error, 80)} />
          <InfoItem label="最近分析" value={compactText(detail.last_analysis_summary, 80)} />
          <InfoItem label="最近行数" value={String(detail.last_row_count ?? "-")} />
        </section>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <TrendChartCard
          title="今日总消耗金额"
          description="默认展示从当前时间往回最近 12 小时，支持手机端全屏查看。"
          data={currentSpendChartData}
          color="var(--color-chart-1)"
          emptyText="当前时间往回最近 12 小时内采样点不足，暂时无法生成今日总消耗趋势图。"
          valueLabel="元"
        />
        <TrendChartCard
          title={`${windowMinutes} 分钟窗口消耗监控`}
          description="默认展示从当前时间往回最近 12 小时窗口波动，用于观察短周期异常抬升。"
          data={increaseAmountChartData}
          color="var(--color-chart-2)"
          referenceLabel="?????"
          referenceColor="var(--color-chart-4)"
          emptyText={`当前时间往回最近 12 小时内采样点不足，暂时无法生成 ${windowMinutes} 分钟窗口趋势图。`}
          valueLabel="元"
        />
      </section>

      <section className="section-grid">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>最近分析</CardTitle>
            <CardDescription>优先查看最近的模型结论、风险级别和摘要。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.recent_analyses.map((item) => (
              <div key={item.id} className="rounded-2xl border border-border/70 bg-background/80 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-medium">{item.summary || "-"}</div>
                  <AlertSeverityBadge severity={item.severity} />
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {formatDateTime(item.created_at)} / {item.provider} / {item.model}
                </div>
                <div className="mt-2 text-sm leading-6 text-foreground">{compactText(item.raw_text, 180)}</div>
              </div>
            ))}
            {detail.recent_analyses.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/80 px-4 py-10 text-center text-sm text-muted-foreground">
                最近还没有分析记录。
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>最近告警</CardTitle>
            <CardDescription>确认这个实例是否真正触发并发出了通知。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {detail.recent_alerts.map((alert) => (
              <div key={alert.id} className="rounded-2xl border border-border/70 bg-background/80 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-medium">{alert.title}</div>
                  <AlertStatusBadge status={alert.send_status} />
                  <AlertSeverityBadge severity={alert.severity} />
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {formatAlertKind(alert.alert_kind)} / {alert.channel || "-"} / {formatDateTime(alert.triggered_at)}
                </div>
                <div className="mt-2 text-sm leading-6 text-foreground">{compactText(alert.content_preview, 180)}</div>
              </div>
            ))}
            {detail.recent_alerts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/80 px-4 py-10 text-center text-sm text-muted-foreground">
                最近没有告警记录。
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <Card className="soft-panel">
        <CardHeader>
          <CardTitle>最近错误</CardTitle>
          <CardDescription>如果这里持续报错，优先检查页面结构变化和采样选择器。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {detail.recent_errors.map((item) => (
            <div key={item.id} className="rounded-2xl border border-border/70 bg-background/80 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="font-medium">{item.error_type}</div>
                <AlertSeverityBadge severity="high" />
              </div>
              <div className="mt-2 text-sm text-muted-foreground">{formatDateTime(item.occurred_at)}</div>
              <div className="mt-2 text-sm leading-6 text-foreground">{compactText(item.error_message, 220)}</div>
            </div>
          ))}
          {detail.recent_errors.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/80 px-4 py-10 text-center text-sm text-muted-foreground">
              最近没有错误记录。
            </div>
          ) : null}
        </CardContent>
      </Card>
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
    <div className="info-item">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-2 text-sm font-medium leading-6 text-foreground">{value}</div>
    </div>
  )
}
