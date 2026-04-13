import { Download, RefreshCcw, RotateCcw } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { AlertSeverityBadge, AlertStatusBadge } from "@/components/alert-badges"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { adminApi } from "@/lib/api"
import { compactText, formatAccountIdentity, formatAlertKind, formatDateTime, formatDisplayName } from "@/lib/format"
import type { AdminAlertRecord, AlertsFilters } from "@/lib/types"
import { cn } from "@/lib/utils"

function getTodayRange() {
  const today = new Date()
  const value = today.toLocaleDateString("en-CA")
  return { dateFrom: value, dateTo: value }
}

const defaultFilters: AlertsFilters = {
  accountKeyword: "",
  sendStatus: "",
  alertKind: "",
  ...getTodayRange(),
}

export function AlertsPage() {
  const [filters, setFilters] = useState<AlertsFilters>(defaultFilters)
  const [alerts, setAlerts] = useState<AdminAlertRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedInstanceId, setSelectedInstanceId] = useState<string>("")

  const load = async () => {
    try {
      setError(null)
      setAlerts(await adminApi.getAlerts(filters))
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载告警记录失败")
    }
  }

  useEffect(() => {
    let active = true

    void adminApi
      .getAlerts(filters)
      .then((result) => {
        if (!active) return
        setError(null)
        setAlerts(result)
      })
      .catch((loadError) => {
        if (!active) return
        setError(loadError instanceof Error ? loadError.message : "加载告警记录失败")
      })

    return () => {
      active = false
    }
  }, [filters])

  const instanceOptions = useMemo(() => {
    const seen = new Set<string>()
    const options: Array<{ instanceId: string; label: string; hint: string; count: number }> = []

    alerts.forEach((alert) => {
      if (!alert.instance_id || seen.has(alert.instance_id)) return
      seen.add(alert.instance_id)

      const related = alerts.filter((item) => item.instance_id === alert.instance_id)
      options.push({
        instanceId: alert.instance_id,
        label: formatDisplayName(alert.account_name, alert.account_id),
        hint: alert.page_type || alert.instance_id,
        count: related.length,
      })
    })

    return options
  }, [alerts])

  const visibleAlerts = useMemo(() => {
    const activeInstanceId =
      selectedInstanceId && instanceOptions.some((item) => item.instanceId === selectedInstanceId)
        ? selectedInstanceId
        : (instanceOptions[0]?.instanceId ?? "")

    if (!activeInstanceId) return alerts
    return alerts.filter((item) => item.instance_id === activeInstanceId)
  }, [alerts, instanceOptions, selectedInstanceId])

  const stats = useMemo(() => {
    const sent = alerts.filter((item) => item.send_status === "sent").length
    const failed = alerts.filter((item) => item.send_status === "failed").length
    const skipped = alerts.filter((item) => item.send_status === "skipped").length
    return { sent, failed, skipped }
  }, [alerts])

  const activeInstanceId =
    selectedInstanceId && instanceOptions.some((item) => item.instanceId === selectedInstanceId)
      ? selectedInstanceId
      : (instanceOptions[0]?.instanceId ?? "")

  const selectedInstance = instanceOptions.find((item) => item.instanceId === activeInstanceId) ?? null

  return (
    <div className="space-y-6">
      <Card className="soft-panel">
        <CardHeader className="gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle>筛选条件</CardTitle>
            <CardDescription>按账户关键词、发送状态、告警类型和日期范围筛选历史告警。</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setFilters({ ...defaultFilters })}>
              <RotateCcw className="size-4" />
              清空
            </Button>
            <Button variant="outline" onClick={() => void load()}>
              <RefreshCcw className="size-4" />
              刷新
            </Button>
            <a href={adminApi.buildAlertsExportHref(filters)} className={buttonVariants({ variant: "default", size: "sm" })}>
              <Download className="size-4" />
              导出 CSV
            </a>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Input
            value={filters.accountKeyword}
            onChange={(event) => setFilters((current) => ({ ...current, accountKeyword: event.target.value }))}
            placeholder="账户名、账户 ID 或实例 ID"
          />
          <Select
            value={filters.sendStatus || "all"}
            onValueChange={(value) =>
              setFilters((current) => ({ ...current, sendStatus: value === "all" ? "" : (value as AlertsFilters["sendStatus"]) }))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="发送状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="sent">已发送</SelectItem>
              <SelectItem value="failed">发送失败</SelectItem>
              <SelectItem value="skipped">已跳过</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={filters.alertKind}
            onChange={(event) => setFilters((current) => ({ ...current, alertKind: event.target.value }))}
            placeholder="例如：threshold / offline"
          />
          <Input
            type="date"
            value={filters.dateFrom}
            onChange={(event) => setFilters((current) => ({ ...current, dateFrom: event.target.value }))}
          />
          <Input
            type="date"
            value={filters.dateTo}
            onChange={(event) => setFilters((current) => ({ ...current, dateTo: event.target.value }))}
          />
        </CardContent>
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard title="当前结果" value={String(alerts.length)} hint="筛选后的告警记录总数" />
        <StatCard title="已发送" value={String(stats.sent)} hint="成功投递的告警记录" />
        <StatCard title="发送失败" value={String(stats.failed)} hint="需要重点排查的投递失败记录" />
        <StatCard title="已跳过" value={String(stats.skipped)} hint="被规则或冷却策略跳过的记录" />
      </section>

      <Card className="soft-panel">
        <CardHeader className="gap-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <CardTitle>告警历史</CardTitle>
              <CardDescription>
                默认展示今天的全部告警，并自动定位到第一个实例。下方可快速切换实例视角。
              </CardDescription>
            </div>
            {selectedInstance ? (
              <div className="rounded-2xl bg-muted/65 px-4 py-3 text-right">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">当前实例</div>
                <div className="mt-1 text-sm font-semibold text-foreground">{selectedInstance.label}</div>
                <div className="mt-1 text-xs text-muted-foreground">{selectedInstance.count} 条记录</div>
              </div>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="text-sm text-rose-600 dark:text-rose-300">{error}</div> : null}

          <div className="space-y-3 md:hidden">
            {visibleAlerts.map((alert) => (
              <AlertHistoryCard key={alert.id} alert={alert} />
            ))}
            {visibleAlerts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/80 px-4 py-10 text-center text-sm text-muted-foreground">
                当前筛选条件下没有告警记录。
              </div>
            ) : null}
          </div>

          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>告警</TableHead>
                  <TableHead>账户</TableHead>
                  <TableHead>级别</TableHead>
                  <TableHead>发送状态</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>触发时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleAlerts.map((alert) => (
                  <TableRow key={alert.id}>
                    <TableCell className="whitespace-normal">
                      <div className="font-medium">{alert.title}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{compactText(alert.content_preview, 120)}</div>
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      {formatAccountIdentity(alert.account_name, alert.account_id)}
                    </TableCell>
                    <TableCell>
                      <AlertSeverityBadge severity={alert.severity} />
                    </TableCell>
                    <TableCell>
                      <AlertStatusBadge status={alert.send_status} />
                    </TableCell>
                    <TableCell>{formatAlertKind(alert.alert_kind)}</TableCell>
                    <TableCell>{formatDateTime(alert.triggered_at)}</TableCell>
                  </TableRow>
                ))}
                {visibleAlerts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="whitespace-normal py-10 text-center text-muted-foreground">
                      当前筛选条件下没有告警记录。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>

          {instanceOptions.length > 0 ? (
            <div className="instance-switcher">
              {instanceOptions.map((item) => {
                const active = item.instanceId === activeInstanceId
                return (
                  <button
                    key={item.instanceId}
                    type="button"
                    onClick={() => setSelectedInstanceId(item.instanceId)}
                    className={cn(
                      "rounded-full border px-4 py-2 text-left transition-colors",
                      active
                        ? "border-primary/30 bg-primary text-primary-foreground shadow-[0_8px_24px_rgba(13,148,136,0.22)]"
                        : "border-border/70 bg-background/90 text-foreground hover:bg-muted/70",
                    )}
                  >
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className={cn("block text-xs", active ? "text-primary-foreground/80" : "text-muted-foreground")}>
                      {item.hint} · {item.count} 条
                    </span>
                  </button>
                )
              })}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({ title, value, hint }: { title: string; value: string; hint: string }) {
  return (
    <Card className="soft-panel">
      <CardHeader className="pb-2">
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-3xl">{value}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">{hint}</CardContent>
    </Card>
  )
}

function AlertHistoryCard({ alert }: { alert: AdminAlertRecord }) {
  return (
    <div className="record-card">
      <div className="flex flex-wrap items-center gap-2">
        <div className="font-medium">{alert.title}</div>
        <AlertStatusBadge status={alert.send_status} />
        <AlertSeverityBadge severity={alert.severity} />
      </div>
      <div className="mt-2 text-sm text-muted-foreground">{formatAccountIdentity(alert.account_name, alert.account_id)}</div>
      <div className="mt-1 text-sm text-muted-foreground">
        {formatAlertKind(alert.alert_kind)} / {formatDateTime(alert.triggered_at)}
      </div>
      <div className="mt-2 text-sm leading-6 text-foreground">{compactText(alert.content_preview, 160)}</div>
    </div>
  )
}
