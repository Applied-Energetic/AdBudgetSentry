import { Activity, AlertTriangle, BarChart3, PencilLine, Server, Wifi, WifiOff } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

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
  formatCurrency,
  formatDateTime,
  formatDisplayName,
  getCaptureStatusLabel,
} from "@/lib/format"
import type { AdminInstanceDetail, DashboardPayload } from "@/lib/types"
import { cn } from "@/lib/utils"

const CONNECTIVITY_WINDOW_MS = 30 * 60 * 1000

export function DashboardPage() {
  const [data, setData] = useState<DashboardPayload | null>(null)
  const [spotlights, setSpotlights] = useState<AdminInstanceDetail[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      setData(await adminApi.getDashboard())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败")
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    const spotlightIds = data?.instances.slice(0, 2).map((instance) => instance.instance_id) ?? []
    if (spotlightIds.length === 0) {
      setSpotlights([])
      return
    }

    let active = true
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

  if (!data && !error) {
    return <div className="page-subheading">正在加载监控总览数据...</div>
  }

  if (error && !data) {
    return (
      <Card className="soft-panel max-w-xl">
        <CardHeader>
          <CardTitle>总览加载失败</CardTitle>
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
          <h2 className="text-base font-semibold text-foreground">重点实例实时监控</h2>
          <p className="mt-1 text-sm text-muted-foreground">首页优先展示两个重点实例的实时状态、波动额度和最近告警。</p>
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
          hint={`${data.summary.yellow_instances} 个需关注，${data.summary.red_instances} 个风险实例`}
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
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>实例健康分布</CardTitle>
            <CardDescription>按实例健康状态查看当前整体分布。</CardDescription>
          </CardHeader>
          <CardContent className="h-[260px] pt-2 sm:h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={healthDistribution}>
                <CartesianGrid vertical={false} stroke="var(--color-border)" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: "color-mix(in srgb, var(--color-chart-2) 8%, transparent)" }}
                  contentStyle={{
                    borderRadius: 16,
                    border: "1px solid var(--color-border)",
                    background: "var(--color-card)",
                  }}
                />
                <Bar dataKey="value" fill="var(--color-chart-2)" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>告警发送状态</CardTitle>
            <CardDescription>基于最近告警记录统计投递结果。</CardDescription>
          </CardHeader>
          <CardContent className="h-[260px] pt-2 sm:h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={alertDistribution}>
                <CartesianGrid vertical={false} stroke="var(--color-border)" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: "color-mix(in srgb, var(--color-chart-1) 8%, transparent)" }}
                  contentStyle={{
                    borderRadius: 16,
                    border: "1px solid var(--color-border)",
                    background: "var(--color-card)",
                  }}
                />
                <Bar dataKey="value" fill="var(--color-chart-1)" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <Card className="soft-panel">
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>实例监控</CardTitle>
              <CardDescription>按健康状态排序的重点监控对象，可进入实例页修改名称和备注。</CardDescription>
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
                    <div>最近心跳：{formatDateTime(instance.last_heartbeat_at)}</div>
                    <div>采样状态：{getCaptureStatusLabel(instance.last_capture_status)}</div>
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
                      备注
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
              <CardDescription>最近产生的告警与投递状态。</CardDescription>
            </div>
            <Link to="/admin/alerts" className={buttonVariants({ variant: "outline", size: "sm" })}>
              查看全部
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.alerts.slice(0, 6).map((alert) => (
              <div key={alert.id} className="rounded-2xl border border-border/70 bg-background/80 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-medium">{alert.title}</div>
                  <AlertStatusBadge status={alert.send_status} />
                </div>
                <div className="mt-2 text-sm text-muted-foreground">{formatAccountIdentity(alert.account_name, alert.account_id)}</div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {formatAlertKind(alert.alert_kind)} / {formatDateTime(alert.triggered_at)}
                </div>
                <div className="mt-2 text-sm leading-6 text-foreground">{compactText(alert.content_preview, 100)}</div>
              </div>
            ))}
            {data.alerts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/80 px-4 py-10 text-center text-sm text-muted-foreground">
                暂无告警记录。
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

function SpotlightCard({ detail }: { detail: AdminInstanceDetail }) {
  const windowMinutes =
    [...detail.capture_history].sort((left, right) => right.captured_at - left.captured_at).find((item) => item.compare_interval_min)
      ?.compare_interval_min ?? 10
  const latestAlert = detail.recent_alerts[0]
  const isConnected = Boolean(detail.last_heartbeat_at && Date.now() - detail.last_heartbeat_at < CONNECTIVITY_WINDOW_MS)
  const displayName = detail.alias || formatDisplayName(detail.account_name, detail.account_id)

  return (
    <Link to={`/admin/instances/${detail.instance_id}`} className="block">
      <Card className="soft-panel overflow-hidden">
        <CardHeader className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <CardTitle className="line-clamp-1 text-base">{displayName}</CardTitle>
              <CardDescription className="mt-1 line-clamp-1">
                {detail.remarks || formatAccountIdentity(detail.account_name, detail.account_id)}
              </CardDescription>
            </div>
            <HealthBadge status={detail.health_status} />
          </div>
          <div
            className={cn(
              "inline-flex w-fit items-center gap-2 rounded-full px-3 py-1 text-xs font-medium",
              isConnected
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200"
                : "bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-200",
            )}
          >
            {isConnected ? <Wifi className="size-3.5" /> : <WifiOff className="size-3.5" />}
            连通性：{isConnected ? "正常" : "异常"}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-muted/80 p-3">
              <div className="text-xs text-muted-foreground">当前总消耗</div>
              <div className="mt-2 text-lg font-semibold text-foreground">{formatCurrency(detail.latest_current_spend)}</div>
            </div>
            <div className="rounded-2xl bg-muted/80 p-3">
              <div className="text-xs text-muted-foreground">{windowMinutes} 分钟窗口</div>
              <div className="mt-2 text-lg font-semibold text-foreground">{formatCurrency(detail.latest_increase_amount)}</div>
            </div>
          </div>

          <div className="rounded-2xl border border-border/70 bg-background/80 p-3">
            <div className="text-xs text-muted-foreground">最近一次告警</div>
            {latestAlert ? (
              <>
                <div className="mt-2 line-clamp-2 text-sm font-medium text-foreground">
                  {compactText(latestAlert.content_preview || latestAlert.title, 70)}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {formatDateTime(latestAlert.triggered_at)} / {formatAlertKind(latestAlert.alert_kind)}
                </div>
                <div className="mt-2 text-sm text-foreground">涉及额度：{formatCurrency(detail.latest_increase_amount)}</div>
              </>
            ) : (
              <div className="mt-2 text-sm text-muted-foreground">最近没有告警记录。</div>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
