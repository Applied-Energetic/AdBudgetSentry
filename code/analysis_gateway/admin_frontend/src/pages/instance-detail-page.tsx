import { ArrowLeft, RefreshCcw, Send, Trash2 } from "lucide-react"
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
import type { AdminAlertRecord, AdminCaptureHistoryPoint, AdminInstanceDetail, InstanceChatResponse } from "@/lib/types"

const HISTORY_WINDOW_MS = 12 * 60 * 60 * 1000

export function InstanceDetailPage() {
  const navigate = useNavigate()
  const { instanceId = "" } = useParams()
  const [detail, setDetail] = useState<AdminInstanceDetail | null | undefined>(undefined)
  const [history, setHistory] = useState<AdminCaptureHistoryPoint[]>([])
  const [form, setForm] = useState({ alias: "", remarks: "" })
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [chatMessage, setChatMessage] = useState("")
  const [chatLoading, setChatLoading] = useState(false)
  const [chatResult, setChatResult] = useState<InstanceChatResponse | null>(null)

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
      setError(loadError instanceof Error ? loadError.message : "加载实例详情失败")
    }
  }

  useEffect(() => {
    let active = true

    void Promise.all([adminApi.getInstanceDetail(instanceId), adminApi.getInstanceHistory(instanceId, 500).catch(() => [])])
      .then(([detailResult, historyResult]) => {
        if (!active) return
        setError(null)
        setDetail(detailResult)
        setHistory(historyResult)
        if (detailResult) {
          setForm({
            alias: detailResult.alias || "",
            remarks: detailResult.remarks || "",
          })
        }
      })
      .catch((loadError) => {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : "加载实例详情失败")
      })

    return () => {
      active = false
    }
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
    const latestWithWindow = [...history]
      .sort((left, right) => right.captured_at - left.captured_at)
      .find((item) => item.compare_interval_min)
    return latestWithWindow?.compare_interval_min ?? 10
  }, [history])

  const recentMailAlerts = useMemo(() => {
    return [...(detail?.recent_alerts ?? [])]
      .filter((alert) => (alert.channel || "").toLowerCase() === "mail")
      .sort((left, right) => {
        if (left.send_status === right.send_status) {
          return right.triggered_at - left.triggered_at
        }
        if (left.send_status === "sent") return -1
        if (right.send_status === "sent") return 1
        return right.triggered_at - left.triggered_at
      })
  }, [detail?.recent_alerts])

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

  const deleteInstance = async () => {
    if (!window.confirm("删除后将移除当前实例的管理记录，是否继续？")) {
      return
    }

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

  const sendChat = async () => {
    const message = chatMessage.trim()
    if (!message) return

    try {
      setChatLoading(true)
      setError(null)
      const result = await adminApi.chatWithInstance(instanceId, message)
      setChatResult(result)
    } catch (chatError) {
      setError(chatError instanceof Error ? chatError.message : "实例聊天失败")
    } finally {
      setChatLoading(false)
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

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricValueCard title="最新总消耗" value={formatCurrency(detail.latest_current_spend)} />
        <MetricValueCard title={`${windowMinutes} 分钟窗口增量`} value={formatCurrency(detail.latest_increase_amount)} />
        <MetricValueCard title="最近采样时间" value={formatDateTime(detail.last_capture_at)} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>实例信息</CardTitle>
            <CardDescription>维护实例别名和备注，方便在告警页和详情页快速识别。</CardDescription>
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
                placeholder="例如：旗舰店投放页"
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
                placeholder="补充当前实例的业务用途、负责人或排查背景。"
              />
            </div>
            <Button onClick={() => void saveMeta()} disabled={saving}>
              {saving ? "保存中..." : "保存实例信息"}
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
          title="总消耗趋势"
          description="聚焦最近 12 小时的采样变化，用于判断消耗是否持续上涨。"
          data={currentSpendChartData}
          color="var(--color-chart-1)"
          emptyText="最近 12 小时内没有足够的采样点，暂时无法绘制总消耗趋势。"
          valueLabel="元"
        />
        <TrendChartCard
          title={`${windowMinutes} 分钟增量趋势`}
          description="结合基线增量一起观察，判断当前波动是正常起伏还是异常加速。"
          data={increaseAmountChartData}
          color="var(--color-chart-2)"
          referenceLabel="基线增量"
          referenceColor="var(--color-chart-4)"
          emptyText={`最近 12 小时内没有足够的采样点，暂时无法绘制 ${windowMinutes} 分钟增量趋势。`}
          valueLabel="元"
        />
      </section>

      <Card className="soft-panel">
        <CardHeader>
          <CardTitle>DeepSeek 实例分析</CardTitle>
          <CardDescription>可直接针对当前实例提问，让模型结合最近采样、分析与告警上下文给出判断。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={chatMessage}
            onChange={(event) => setChatMessage(event.target.value)}
            placeholder="例如：请结合最近 30 分钟的采样和告警，判断当前风险是否需要人工介入。"
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button onClick={() => void sendChat()} disabled={chatLoading || !chatMessage.trim()}>
              <Send className="size-4" />
              {chatLoading ? "分析中..." : "发送给 DeepSeek"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setChatMessage("请基于最近采样、分析和告警，给出当前实例的风险判断、可能原因和下一步建议。")}
            >
              使用建议问题
            </Button>
          </div>

          {chatResult ? (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
              <div className="record-card">
                <div className="text-sm font-medium text-foreground">
                  模型回复
                  <span className="ml-2 text-xs text-muted-foreground">
                    {chatResult.provider} / {chatResult.model}
                  </span>
                </div>
                <div className="mt-3 whitespace-pre-wrap text-sm leading-7 text-foreground">{chatResult.reply}</div>
              </div>
              <div className="record-card">
                <div className="text-sm font-medium text-foreground">上下文摘要</div>
                <div className="mt-3 whitespace-pre-wrap text-xs leading-6 text-muted-foreground">{chatResult.context_preview}</div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="soft-panel">
        <CardHeader>
          <CardTitle>最近邮件告警</CardTitle>
          <CardDescription>仅保留最近生成的邮件告警，优先展示已发送结果，减少分析和错误信息对观察的干扰。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {recentMailAlerts.map((alert) => (
            <InstanceAlertCard key={alert.id} alert={alert} />
          ))}
          {recentMailAlerts.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/80 px-4 py-10 text-center text-sm text-muted-foreground">
              最近没有邮件告警记录。
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

function InstanceAlertCard({ alert }: { alert: AdminAlertRecord }) {
  return (
    <div className="record-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <div className="font-medium text-foreground">{alert.title}</div>
            <AlertStatusBadge status={alert.send_status} />
            <AlertSeverityBadge severity={alert.severity} />
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded-full bg-muted/60 px-3 py-1">{formatAlertKind(alert.alert_kind)}</span>
            <span className="rounded-full bg-muted/60 px-3 py-1">{alert.channel || "-"}</span>
            <span className="rounded-full bg-muted/60 px-3 py-1">{formatDateTime(alert.triggered_at)}</span>
          </div>
        </div>
      </div>
      <div className="mt-3 text-sm leading-6 text-foreground">{compactText(alert.content_preview, 240)}</div>
    </div>
  )
}
