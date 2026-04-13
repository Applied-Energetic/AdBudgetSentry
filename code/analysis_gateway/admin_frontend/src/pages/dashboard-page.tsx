import { Activity, AlertTriangle, BarChart3, PencilLine, Server } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { AlertStatusBadge } from "@/components/alert-badges"
import { HealthBadge } from "@/components/health-badge"
import { MetricCard } from "@/components/metric-card"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { adminApi } from "@/lib/api"
import {
  compactText,
  formatAccountIdentity,
  formatAlertKind,
  formatDateTime,
  formatDisplayName,
  getCaptureStatusLabel,
  getSendStatusLabel,
} from "@/lib/format"
import type { AdminAlertRecord, AdminInstanceDetail, DashboardPayload } from "@/lib/types"
import { cn } from "@/lib/utils"

const healthChartPalette = ["var(--color-chart-3)", "var(--color-chart-2)", "var(--color-chart-4)"]
const alertChartPalette = ["var(--color-chart-1)", "var(--color-chart-4)", "var(--color-chart-3)"]

export function DashboardPage() {
  const [data, setData] = useState<DashboardPayload | null>(null)
  const [spotlights, setSpotlights] = useState<AdminInstanceDetail[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setData(await adminApi.getDashboard())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载监控总览失败")
    }
  }

  useEffect(() => {
    let active = true

    void adminApi
      .getDashboard()
      .then((result) => {
        if (!active) return
        setError(null)
        setData(result)
      })
      .catch((loadError) => {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : "加载监控总览失败")
      })

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const spotlightIds = data?.instances.slice(0, 2).map((instance) => instance.instance_id) ?? []
    if (spotlightIds.length === 0) {
      queueMicrotask(() => {
        if (active) setSpotlights([])
      })
      return
    }

    void Promise.all(spotlightIds.map((id) => adminApi.getInstanceDetail(id).catch(() => null))).then((results) => {
      if (!active) return
      setSpotlights(results.filter((item): item is AdminInstanceDetail => Boolean(item)))
    })

    return () => {
      active = false
    }
  }, [data?.instances])

  const healthDistribution = useMemo(() => {
    if (!data) return []
    return [
      { label: "健康", value: data.summary.green_instances },
      { label: "关注", value: data.summary.yellow_instances },
      { label: "风险", value: data.summary.red_instances },
    ]
  }, [data])

  const alertDistribution = useMemo(() => {
    if (!data) return []
    const counts = { sent: 0, failed: 0, skipped: 0 }
    for (const item of data.alerts) {
      counts[item.send_status] += 1
    }
    return [
      { label: "已发送", value: counts.sent },
      { label: "发送失败", value: counts.failed },
      { label: "已跳过", value: counts.skipped },
    ]
  }, [data])

  const dominantHealth = useMemo(() => getDominantItem(healthDistribution), [healthDistribution])
  const dominantAlert = useMemo(() => getDominantItem(alertDistribution), [alertDistribution])

  if (!data && !error) {
    return <div className="page-subheading">正在加载监控总览...</div>
  }

  if (error && !data) {
    return (
      <Card className="soft-panel max-w-xl">
        <CardHeader>
          <CardTitle>加载监控总览失败</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void load()}>重新加载</Button>
        </CardContent>
      </Card>
    )
  }

  if (!data) {
    return null
  }

  return (
    <div className="space-y-6">
      <section className="space-y-3 md:hidden">
        <div>
          <h2 className="text-base font-semibold text-foreground">重点实例</h2>
          <p className="mt-1 text-sm text-muted-foreground">优先查看当前风险或需要关注的实例，便于快速进入详情确认告警原因。</p>
        </div>
        {spotlights.map((detail) => (
          <SpotlightCard key={detail.instance_id} detail={detail} />
        ))}
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="在线实例"
          value={String(data.summary.total_instances)}
          hint={`最近心跳 ${formatDateTime(data.summary.latest_heartbeat_at)}`}
          icon={<Server className="size-5" />}
          tone="teal"
        />
        <MetricCard
          title="健康实例"
          value={String(data.summary.green_instances)}
          hint={`${data.summary.yellow_instances} 个关注，${data.summary.red_instances} 个风险实例`}
          icon={<Activity className="size-5" />}
          tone="green"
        />
        <MetricCard
          title="分析记录"
          value={String(data.summary.total_analyses)}
          hint={`最近采样 ${formatDateTime(data.summary.latest_capture_at)}`}
          icon={<BarChart3 className="size-5" />}
          tone="orange"
        />
        <MetricCard
          title="告警记录"
          value={String(data.summary.total_alerts)}
          hint={`最近告警 ${formatDateTime(data.summary.latest_alert_at)}`}
          icon={<AlertTriangle className="size-5" />}
          tone="magenta"
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <DistributionCard
          title="实例健康分布"
          description="按实例健康状态查看当前业务体征，减少大面积留白并强化重点状态。"
          total={data.summary.total_instances}
          kicker="实例总数"
          dominantLabel={dominantHealth.label}
          dominantValue={dominantHealth.value}
          dominantHint="当前占比最高的体征"
          data={healthDistribution}
          palette={healthChartPalette}
          footerItems={[
            { label: "健康", value: `${data.summary.green_instances} 个` },
            { label: "关注", value: `${data.summary.yellow_instances} 个` },
            { label: "风险", value: `${data.summary.red_instances} 个` },
          ]}
        />

        <DistributionCard
          title="告警发送状态"
          description="聚焦今天最新告警的投递结果，让成功、失败和跳过一眼可见。"
          total={data.alerts.length}
          kicker="今日告警"
          dominantLabel={dominantAlert.label}
          dominantValue={dominantAlert.value}
          dominantHint="当前数量最多的发送状态"
          data={alertDistribution}
          palette={alertChartPalette}
          footerItems={alertDistribution.map((item) => ({
            label: item.label,
            value: `${item.value} 条`,
          }))}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Card className="soft-panel">
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>实例监控</CardTitle>
              <CardDescription>按临时状态排序的重点监控对象，可进入实例页修改名称和备注。</CardDescription>
            </div>
            <Button variant="outline" onClick={() => void load()}>
              刷新
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-3 md:hidden">
              {data.instances.slice(0, 8).map((instance) => (
                <div key={instance.instance_id} className="rounded-2xl border border-border/70 bg-background/90 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium">{instance.alias || formatDisplayName(instance.account_name, instance.account_id)}</div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        {compactText(instance.remarks || formatAccountIdentity(instance.account_name, instance.account_id), 56)}
                      </div>
                    </div>
                    <HealthBadge status={instance.health_status} />
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-muted-foreground">
                    <div>最近心跳 {formatDateTime(instance.last_heartbeat_at)}</div>
                    <div>采样状态 {getCaptureStatusLabel(instance.last_capture_status)}</div>
                  </div>
                  <div className="mt-4 flex gap-2">
                    <Link
                      to={`/admin/instances/${instance.instance_id}`}
                      className={cn(buttonVariants({ variant: "default", size: "sm" }), "flex-1 rounded-full")}
                    >
                      查看详情
                    </Link>
                    <Link
                      to={`/admin/instances/${instance.instance_id}`}
                      className={cn(buttonVariants({ variant: "outline", size: "sm" }), "rounded-full")}
                    >
                      <PencilLine className="size-4" />
                      编辑
                    </Link>
                  </div>
                </div>
              ))}
            </div>

            <div className="hidden md:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>实例</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>最近心跳</TableHead>
                    <TableHead>采样状态</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.instances.slice(0, 8).map((instance) => (
                    <TableRow key={instance.instance_id}>
                      <TableCell className="whitespace-normal">
                        <div className="font-medium">{instance.alias || formatDisplayName(instance.account_name, instance.account_id)}</div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {compactText(instance.remarks || formatAccountIdentity(instance.account_name, instance.account_id), 60)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <HealthBadge status={instance.health_status} />
                      </TableCell>
                      <TableCell>{formatDateTime(instance.last_heartbeat_at)}</TableCell>
                      <TableCell>{getCaptureStatusLabel(instance.last_capture_status)}</TableCell>
                      <TableCell>
                        <Link
                          to={`/admin/instances/${instance.instance_id}`}
                          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "rounded-full")}
                        >
                          查看详情
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card className="soft-panel">
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>最新告警</CardTitle>
              <CardDescription>展示今天发生的最新告警与投递状态，保留摘要层次并增强扫读性。</CardDescription>
            </div>
            <Link to="/admin/alerts" className={buttonVariants({ variant: "outline", size: "sm" })}>
              查看全部
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.alerts.slice(0, 6).map((alert) => (
              <AlertDigestCard key={alert.id} alert={alert} />
            ))}
            {data.alerts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/80 px-4 py-10 text-center text-sm text-muted-foreground">
                今天还没有告警记录。
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

function DistributionCard({
  title,
  description,
  total,
  kicker,
  dominantLabel,
  dominantValue,
  dominantHint,
  data,
  palette,
  footerItems,
}: {
  title: string
  description: string
  total: number
  kicker: string
  dominantLabel: string
  dominantValue: number
  dominantHint: string
  data: Array<{ label: string; value: number }>
  palette: string[]
  footerItems: Array<{ label: string; value: string }>
}) {
  return (
    <Card className="soft-panel overflow-hidden">
      <CardContent className="p-4 sm:p-5">
        <div className="chart-panel">
          <div className="chart-panel-header">
            <div className="space-y-1">
              <div className="text-lg font-semibold text-foreground">{title}</div>
              <p className="max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>
            </div>
            <div className="chart-panel-stat">
              <div className="chart-panel-kicker">{kicker}</div>
              <div className="chart-panel-value">{total}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {dominantLabel} {dominantValue}
              </div>
            </div>
          </div>

          <div className="mt-4 h-[220px] sm:h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} barCategoryGap={28} margin={{ top: 12, right: 6, left: -18, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={12} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={34} />
                <Tooltip
                  cursor={{ fill: "color-mix(in srgb, var(--color-primary) 6%, transparent)" }}
                  contentStyle={{
                    borderRadius: 18,
                    border: "1px solid var(--color-border)",
                    background: "color-mix(in srgb, var(--color-card) 96%, white)",
                    boxShadow: "0 18px 40px rgba(15, 23, 42, 0.08)",
                  }}
                />
                <Bar dataKey="value" radius={[12, 12, 4, 4]}>
                  {data.map((entry, index) => (
                    <Cell key={`${entry.label}-${index}`} fill={palette[index % palette.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-panel-footer">
            <div className="chart-panel-footer-item">
              <div className="chart-panel-footer-label">主状态</div>
              <div className="chart-panel-footer-value">{dominantLabel}</div>
            </div>
            <div className="chart-panel-footer-item">
              <div className="chart-panel-footer-label">数量</div>
              <div className="chart-panel-footer-value">{dominantValue}</div>
            </div>
            <div className="chart-panel-footer-item">
              <div className="chart-panel-footer-label">说明</div>
              <div className="chart-panel-footer-value">{dominantHint}</div>
            </div>
            {footerItems.map((item) => (
              <div key={item.label} className="chart-panel-footer-item">
                <div className="chart-panel-footer-label">{item.label}</div>
                <div className="chart-panel-footer-value">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function AlertDigestCard({ alert }: { alert: AdminAlertRecord }) {
  return (
    <div className="record-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <div className="font-medium text-foreground">{alert.title}</div>
            <AlertStatusBadge status={alert.send_status} />
          </div>
          <div className="mt-2 text-sm text-muted-foreground">{formatAccountIdentity(alert.account_name, alert.account_id)}</div>
        </div>
        <div className="rounded-full bg-muted/70 px-3 py-1 text-xs font-medium text-muted-foreground">
          {formatDateTime(alert.triggered_at)}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span className="rounded-full bg-muted/60 px-3 py-1">{formatAlertKind(alert.alert_kind)}</span>
        <span className="rounded-full bg-muted/60 px-3 py-1">{getSendStatusLabel(alert.send_status)}</span>
      </div>

      <div className="mt-3 text-sm leading-6 text-foreground">{compactText(alert.content_preview, 110)}</div>
    </div>
  )
}

function SpotlightCard({ detail }: { detail: AdminInstanceDetail }) {
  return (
    <div className="record-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium">{detail.alias || formatDisplayName(detail.account_name, detail.account_id)}</div>
          <div className="mt-1 text-sm text-muted-foreground">
            {compactText(detail.remarks || formatAccountIdentity(detail.account_name, detail.account_id), 56)}
          </div>
        </div>
        <HealthBadge status={detail.health_status} />
      </div>
      <div className="mt-3 grid gap-2 text-sm text-muted-foreground">
        <div>最近心跳 {formatDateTime(detail.last_heartbeat_at)}</div>
        <div>最近分析 {compactText(detail.last_analysis_summary || "暂无分析摘要", 40)}</div>
      </div>
      <div className="mt-4">
        <Link to={`/admin/instances/${detail.instance_id}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "rounded-full")}>
          查看详情
        </Link>
      </div>
    </div>
  )
}

function getDominantItem(items: Array<{ label: string; value: number }>) {
  const initial = items[0] ?? { label: "-", value: 0 }
  return items.reduce((highest, item) => (item.value > highest.value ? item : highest), initial)
}
