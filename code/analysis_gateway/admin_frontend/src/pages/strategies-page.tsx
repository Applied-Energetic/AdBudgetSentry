import { PencilLine, Plus, RefreshCcw, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { adminApi } from "@/lib/api"
import { formatAccountIdentity, formatDateTime, formatMetricKey, formatStrategyTemplate } from "@/lib/format"
import type { AdminInstanceStrategyRecord, AdminInstanceSummary, MetricRegistryItem } from "@/lib/types"

type StrategyFormState = {
  instanceId: string
  name: string
  description: string
  template_type: "window_threshold" | "historical_baseline"
  target_metric: string
  enabled: boolean
  window_minutes: string
  threshold_value: string
  zscore_threshold: string
  min_samples: string
  cooldown_minutes: string
  severity: "low" | "medium" | "high"
}

const emptyForm: StrategyFormState = {
  instanceId: "",
  name: "",
  description: "",
  template_type: "window_threshold",
  target_metric: "spend",
  enabled: true,
  window_minutes: "10",
  threshold_value: "20",
  zscore_threshold: "2.5",
  min_samples: "3",
  cooldown_minutes: "10",
  severity: "high",
}

function buildPayload(form: StrategyFormState) {
  const baseParams = {
    window_minutes: Number(form.window_minutes) || 10,
    cooldown_minutes: Number(form.cooldown_minutes) || 10,
    severity: form.severity,
  }

  const params =
    form.template_type === "window_threshold"
      ? {
          ...baseParams,
          threshold_value: Number(form.threshold_value) || 0,
        }
      : {
          ...baseParams,
          zscore_threshold: Number(form.zscore_threshold) || 2.5,
          min_samples: Number(form.min_samples) || 3,
        }

  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    template_type: form.template_type,
    target_metric: form.target_metric,
    enabled: form.enabled,
    is_default: false,
    auto_bind_new_instances: false,
    params,
  }
}

function buildForm(record: AdminInstanceStrategyRecord | null): StrategyFormState {
  if (!record) return emptyForm
  const params = record.params || {}
  return {
    instanceId: record.instance_id,
    name: record.strategy_name,
    description: record.description || "",
    template_type: record.template_type,
    target_metric: record.target_metric,
    enabled: record.enabled,
    window_minutes: String(params.window_minutes ?? 10),
    threshold_value: String(params.threshold_value ?? 20),
    zscore_threshold: String(params.zscore_threshold ?? 2.5),
    min_samples: String(params.min_samples ?? 3),
    cooldown_minutes: String(params.cooldown_minutes ?? 10),
    severity: (params.severity as "low" | "medium" | "high") ?? "high",
  }
}

export function StrategiesPage() {
  const [records, setRecords] = useState<AdminInstanceStrategyRecord[]>([])
  const [instances, setInstances] = useState<AdminInstanceSummary[]>([])
  const [metrics, setMetrics] = useState<MetricRegistryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [editing, setEditing] = useState<AdminInstanceStrategyRecord | null>(null)
  const [form, setForm] = useState<StrategyFormState>(emptyForm)

  const strategyReadyMetrics = useMemo(
    () => metrics.filter((item) => item.is_enabled && item.is_strategy_ready),
    [metrics],
  )

  const recordsByInstance = useMemo(() => {
    const grouped = new Map<string, { label: string; accountLine: string; records: AdminInstanceStrategyRecord[] }>()
    for (const record of records) {
      const existing = grouped.get(record.instance_id)
      const accountLine = formatAccountIdentity(record.account_name, record.account_id)
      if (existing) {
        existing.records.push(record)
        continue
      }
      grouped.set(record.instance_id, {
        label: record.instance_label,
        accountLine,
        records: [record],
      })
    }
    return Array.from(grouped.entries()).map(([instanceId, value]) => ({
      instanceId,
      ...value,
      records: value.records.sort((a, b) => a.strategy_name.localeCompare(b.strategy_name, "zh-CN")),
    }))
  }, [records])

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      const [recordData, instanceData, metricData] = await Promise.all([
        adminApi.getInstanceStrategies(),
        adminApi.getInstances(),
        adminApi.getMetrics(),
      ])
      setRecords(recordData)
      setInstances(instanceData)
      setMetrics(metricData)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载实例策略失败")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const save = async () => {
    try {
      setSaving(true)
      setError(null)
      const payload = buildPayload(form)
      if (editing) {
        await adminApi.updateStrategy(editing.strategy_id, payload)
        await adminApi.saveInstanceStrategyBinding(editing.instance_id, {
          strategy_id: editing.strategy_id,
          enabled: form.enabled,
          priority: editing.priority,
        })
        setStatus("实例策略已更新。")
      } else {
        const created = await adminApi.createStrategy(payload)
        await adminApi.saveInstanceStrategyBinding(form.instanceId, {
          strategy_id: created.id,
          enabled: form.enabled,
          priority: 100,
        })
        setStatus("实例策略已创建。")
      }
      setEditing(null)
      setForm(emptyForm)
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存实例策略失败")
    } finally {
      setSaving(false)
    }
  }

  const remove = async (record: AdminInstanceStrategyRecord) => {
    if (!window.confirm(`删除实例策略“${record.strategy_name}”后不会移除历史告警，是否继续？`)) return

    try {
      setError(null)
      await adminApi.deleteStrategy(record.strategy_id)
      if (editing?.strategy_id === record.strategy_id) {
        setEditing(null)
        setForm(emptyForm)
      }
      setStatus("实例策略已删除。")
      await load()
    } catch (removeError) {
      setError(removeError instanceof Error ? removeError.message : "删除实例策略失败")
    }
  }

  const startEdit = (record: AdminInstanceStrategyRecord) => {
    setEditing(record)
    setForm(buildForm(record))
    setStatus(null)
    setError(null)
  }

  const startCreate = () => {
    setEditing(null)
    setForm(emptyForm)
    setStatus(null)
    setError(null)
  }

  if (loading) {
    return <div className="page-subheading">正在加载实例策略...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="page-heading">策略中心</h1>
          <p className="page-subheading">每条策略只对应一个实例。修改时不会影响其他实例，便于单独维护参数。</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCcw className="size-4" />
            刷新
          </Button>
          <Button onClick={startCreate}>
            <Plus className="size-4" />
            新建实例策略
          </Button>
        </div>
      </div>

      {error ? <div className="text-sm text-rose-600 dark:text-rose-300">{error}</div> : null}
      {status ? <div className="text-sm text-emerald-700 dark:text-emerald-300">{status}</div> : null}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>实例策略视图</CardTitle>
            <CardDescription>每个实例一张卡片，只显示它自己的策略。这样修改时不会误伤其他实例。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recordsByInstance.map((group) => (
              <div key={group.instanceId} className="rounded-3xl border border-border/70 bg-background/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold text-foreground">{group.label}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{group.accountLine}</div>
                    <div className="mt-1 text-xs text-muted-foreground">实例 ID：{group.instanceId}</div>
                  </div>
                  <div className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                    策略数：{group.records.length}
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {group.records.map((record) => (
                    <div key={record.id} className="record-card">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-foreground">{record.strategy_name}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {formatStrategyTemplate(record.template_type)} / {formatMetricKey(record.target_metric)}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => startEdit(record)}>
                            <PencilLine className="size-4" />
                            编辑
                          </Button>
                          <Button variant="destructive" size="sm" onClick={() => void remove(record)}>
                            <Trash2 className="size-4" />
                            删除
                          </Button>
                        </div>
                      </div>
                      <div className="mt-3 text-sm text-muted-foreground">{record.description || "暂无描述"}</div>
                      <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                        <div>命中次数：{record.hit_count}</div>
                        <div>启用状态：{record.enabled ? "启用" : "停用"}</div>
                        <div>优先级：{record.priority}</div>
                        <div>更新时间：{formatDateTime(record.updated_at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {recordsByInstance.length === 0 ? <div className="text-sm text-muted-foreground">当前没有实例策略。</div> : null}
          </CardContent>
        </Card>

        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>{editing ? "编辑实例策略" : "新建实例策略"}</CardTitle>
            <CardDescription>新建时必须选择实例，策略创建后只归属于该实例。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">目标实例</label>
              <Select
                value={form.instanceId || "none"}
                onValueChange={(value) => setForm((current) => ({ ...current, instanceId: value === "none" ? "" : String(value) }))}
                disabled={Boolean(editing)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="请选择实例" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">请选择实例</SelectItem>
                  {instances.map((instance) => (
                    <SelectItem key={instance.instance_id} value={instance.instance_id}>
                      {instance.alias || instance.account_name || instance.account_id || instance.instance_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">策略名称</label>
              <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">描述</label>
              <Textarea
                value={form.description}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">模板</label>
                <Select
                  value={form.template_type}
                  onValueChange={(value) =>
                    setForm((current) => ({ ...current, template_type: value as StrategyFormState["template_type"] }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="window_threshold">窗口阈值</SelectItem>
                    <SelectItem value="historical_baseline">历史基线</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">目标指标</label>
                <Select
                  value={form.target_metric}
                  onValueChange={(value) => setForm((current) => ({ ...current, target_metric: String(value ?? "spend") }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {strategyReadyMetrics.map((metric) => (
                      <SelectItem key={metric.metric_key} value={metric.metric_key}>
                        {metric.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <LabeledBoolean
                label="启用策略"
                value={form.enabled}
                onChange={(value) => setForm((current) => ({ ...current, enabled: value }))}
              />
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">严重度</label>
                <Select
                  value={form.severity}
                  onValueChange={(value) => setForm((current) => ({ ...current, severity: value as StrategyFormState["severity"] }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">低</SelectItem>
                    <SelectItem value="medium">中</SelectItem>
                    <SelectItem value="high">高</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <LabeledNumber
                label="窗口分钟数"
                value={form.window_minutes}
                onChange={(value) => setForm((current) => ({ ...current, window_minutes: value }))}
              />
              <LabeledNumber
                label="冷却分钟数"
                value={form.cooldown_minutes}
                onChange={(value) => setForm((current) => ({ ...current, cooldown_minutes: value }))}
              />
              {form.template_type === "window_threshold" ? (
                <LabeledNumber
                  label="阈值"
                  value={form.threshold_value}
                  onChange={(value) => setForm((current) => ({ ...current, threshold_value: value }))}
                />
              ) : (
                <>
                  <LabeledNumber
                    label="Z-Score 阈值"
                    value={form.zscore_threshold}
                    onChange={(value) => setForm((current) => ({ ...current, zscore_threshold: value }))}
                  />
                  <LabeledNumber
                    label="最少样本数"
                    value={form.min_samples}
                    onChange={(value) => setForm((current) => ({ ...current, min_samples: value }))}
                  />
                </>
              )}
            </div>

            <div className="flex gap-2">
              <Button onClick={() => void save()} disabled={saving || !form.name.trim() || !form.instanceId}>
                {saving ? "保存中..." : editing ? "保存修改" : "创建实例策略"}
              </Button>
              {editing ? (
                <Button variant="outline" onClick={startCreate}>
                  取消编辑
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

function LabeledNumber({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <Input type="number" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}

function LabeledBoolean({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <Select value={value ? "true" : "false"} onValueChange={(next) => onChange(next === "true")}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="true">是</SelectItem>
          <SelectItem value="false">否</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}
