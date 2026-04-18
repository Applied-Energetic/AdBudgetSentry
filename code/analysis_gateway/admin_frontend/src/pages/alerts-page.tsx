import { Download, RefreshCcw, RotateCcw } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { AlertSeverityBadge, AlertStatusBadge } from "@/components/alert-badges"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { adminApi } from "@/lib/api"
import {
  compactText,
  formatAccountIdentity,
  formatAlertKind,
  formatDateTime,
  formatMetricKey,
  formatStrategyTemplate,
} from "@/lib/format"
import type { AdminAlertRecord, AlertsFilters, StrategyDefinition } from "@/lib/types"

function getTodayRange() {
  const today = new Date()
  const value = today.toLocaleDateString("en-CA")
  return { dateFrom: value, dateTo: value }
}

const defaultFilters: AlertsFilters = {
  accountKeyword: "",
  sendStatus: "",
  alertKind: "",
  strategyId: "",
  templateType: "",
  targetMetric: "",
  ...getTodayRange(),
}

export function AlertsPage() {
  const [filters, setFilters] = useState<AlertsFilters>(defaultFilters)
  const [alerts, setAlerts] = useState<AdminAlertRecord[]>([])
  const [strategies, setStrategies] = useState<StrategyDefinition[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setError(null)
      const [alertData, strategyData] = await Promise.all([adminApi.getAlerts(filters), adminApi.getStrategies()])
      setAlerts(alertData)
      setStrategies(strategyData)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载告警记录失败")
    }
  }

  useEffect(() => {
    void load()
  }, [filters])

  const stats = useMemo(() => {
    const sent = alerts.filter((item) => item.send_status === "sent").length
    const failed = alerts.filter((item) => item.send_status === "failed").length
    const skipped = alerts.filter((item) => item.send_status === "skipped").length
    return { sent, failed, skipped }
  }, [alerts])

  return (
    <div className="space-y-6">
      <Card className="soft-panel">
        <CardHeader className="gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle>筛选条件</CardTitle>
            <CardDescription>按账户、告警状态、策略、模板、指标和日期范围筛选历史告警。</CardDescription>
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
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Input
            value={filters.accountKeyword}
            onChange={(event) => setFilters((current) => ({ ...current, accountKeyword: event.target.value }))}
            placeholder="账户名称、账户 ID 或实例 ID"
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
            placeholder="例如 threshold / strategy:1"
          />
          <Select
            value={filters.strategyId || "all"}
            onValueChange={(value) => setFilters((current) => ({ ...current, strategyId: value === "all" ? "" : String(value ?? "") }))}
          >
            <SelectTrigger>
              <SelectValue placeholder="策略" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部策略</SelectItem>
              {strategies.map((strategy) => (
                <SelectItem key={strategy.id} value={String(strategy.id)}>
                  {strategy.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={filters.templateType || "all"}
            onValueChange={(value) =>
              setFilters((current) => ({ ...current, templateType: value === "all" ? "" : String(value ?? "") }))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="模板" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部模板</SelectItem>
              <SelectItem value="window_threshold">窗口阈值</SelectItem>
              <SelectItem value="historical_baseline">历史基线</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filters.targetMetric || "all"}
            onValueChange={(value) =>
              setFilters((current) => ({ ...current, targetMetric: value === "all" ? "" : String(value ?? "") }))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="指标" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部指标</SelectItem>
              <SelectItem value="spend">花费</SelectItem>
            </SelectContent>
          </Select>
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
        <StatCard title="已发送" value={String(stats.sent)} hint="成功投递的告警" />
        <StatCard title="发送失败" value={String(stats.failed)} hint="需要重点排查的失败记录" />
        <StatCard title="已跳过" value={String(stats.skipped)} hint="因冷却或配置原因跳过的记录" />
      </section>

      <Card className="soft-panel">
        <CardHeader>
          <CardTitle>告警历史</CardTitle>
          <CardDescription>所有策略告警和系统告警都在这里回看，并保留策略来源链路。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="text-sm text-rose-600 dark:text-rose-300">{error}</div> : null}

          <div className="space-y-3 md:hidden">
            {alerts.map((alert) => (
              <AlertHistoryCard key={alert.id} alert={alert} />
            ))}
            {alerts.length === 0 ? (
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
                  <TableHead>策略</TableHead>
                  <TableHead>模板 / 指标</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>级别</TableHead>
                  <TableHead>触发时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {alerts.map((alert) => (
                  <TableRow key={alert.id}>
                    <TableCell className="whitespace-normal">
                      <div className="font-medium">{alert.title}</div>
                      <div className="mt-1 text-sm text-muted-foreground">{compactText(alert.content_preview, 120)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatAlertKind(alert.alert_kind)}</div>
                    </TableCell>
                    <TableCell className="whitespace-normal">{formatAccountIdentity(alert.account_name, alert.account_id)}</TableCell>
                    <TableCell className="whitespace-normal">{alert.strategy_name || "系统告警"}</TableCell>
                    <TableCell className="whitespace-normal">
                      {alert.template_type ? formatStrategyTemplate(alert.template_type) : "-"} / {formatMetricKey(alert.target_metric)}
                    </TableCell>
                    <TableCell>
                      <AlertStatusBadge status={alert.send_status} />
                    </TableCell>
                    <TableCell>
                      <AlertSeverityBadge severity={alert.severity} />
                    </TableCell>
                    <TableCell>{formatDateTime(alert.triggered_at)}</TableCell>
                  </TableRow>
                ))}
                {alerts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="whitespace-normal py-10 text-center text-muted-foreground">
                      当前筛选条件下没有告警记录。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
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
        {alert.strategy_name || "系统告警"} / {formatDateTime(alert.triggered_at)}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        {alert.template_type ? formatStrategyTemplate(alert.template_type) : "-"} / {formatMetricKey(alert.target_metric)}
      </div>
      <div className="mt-2 text-sm leading-6 text-foreground">{compactText(alert.content_preview, 160)}</div>
    </div>
  )
}
