import { RefreshCcw, Save, Send, Sparkles } from "lucide-react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { adminApi } from "@/lib/api"
import type { AdminSystemSettings, ProviderConnectivityResponse } from "@/lib/types"

const emptySettings: AdminSystemSettings = {
  default_provider: "deepseek",
  deepseek: {
    base_url: "https://api.deepseek.com",
    model: "deepseek-chat",
    api_key: "",
  },
  local: {
    base_url: "http://127.0.0.1:11434/v1",
    model: "qwen2.5:3b-instruct",
    api_key: "",
  },
  pushplus: {
    enabled: true,
    channel: "mail",
    channel_option: "",
    has_token: false,
    token_preview: null,
    token: "",
  },
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AdminSystemSettings>(emptySettings)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testingPushplus, setTestingPushplus] = useState(false)
  const [testingDeepseek, setTestingDeepseek] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [deepseekStatus, setDeepseekStatus] = useState<ProviderConnectivityResponse | null>(null)

  const load = async () => {
    try {
      setLoading(true)
      setError(null)
      setStatus(null)
      setSettings(await adminApi.getSettings())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载系统设置失败")
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
      setStatus(null)
      const result = await adminApi.updateSettings(settings)
      setSettings(result)
      setStatus("配置已保存，后续请求会自动读取最新设置。")
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存设置失败")
    } finally {
      setSaving(false)
    }
  }

  const testPushplus = async () => {
    try {
      setTestingPushplus(true)
      setError(null)
      const result = await adminApi.testPushplus()
      setStatus(result.ok ? "PushPlus 测试消息已提交，请检查目标通道。" : result.message || "PushPlus 测试失败")
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : "PushPlus 测试失败")
    } finally {
      setTestingPushplus(false)
    }
  }

  const testDeepseek = async () => {
    try {
      setTestingDeepseek(true)
      setError(null)
      const result = await adminApi.testDeepseek()
      setDeepseekStatus(result)
      setStatus(`DeepSeek 连通成功，当前模型：${result.model}`)
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : "DeepSeek 连通性测试失败")
    } finally {
      setTestingDeepseek(false)
    }
  }

  const updateProviderField = (provider: "deepseek" | "local", key: "base_url" | "model" | "api_key", value: string) => {
    setSettings((current) => ({
      ...current,
      [provider]: {
        ...current[provider],
        [key]: value,
      },
    }))
  }

  if (loading) {
    return <div className="page-subheading">正在加载系统设置...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="page-heading">系统设置</h1>
          <p className="page-subheading">
            在这里统一管理 PushPlus 告警通道、默认分析提供方，以及 DeepSeek / 本地模型的连接参数。
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="outline" onClick={() => void load()} disabled={loading || saving}>
            <RefreshCcw className="size-4" />
            刷新配置
          </Button>
          <Button onClick={() => void save()} disabled={saving}>
            <Save className="size-4" />
            {saving ? "保存中..." : "保存配置"}
          </Button>
        </div>
      </div>

      {error ? <div className="text-sm text-rose-600 dark:text-rose-300">{error}</div> : null}
      {status ? <div className="text-sm text-emerald-700 dark:text-emerald-300">{status}</div> : null}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>PushPlus 告警</CardTitle>
            <CardDescription>这里的配置由后端直接用于调用 PushPlus API 发送邮件或微信消息。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">是否启用</label>
                <Select
                  value={settings.pushplus.enabled ? "true" : "false"}
                  onValueChange={(value) =>
                    setSettings((current) => ({
                      ...current,
                      pushplus: {
                        ...current.pushplus,
                        enabled: value === "true",
                      },
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">启用</SelectItem>
                    <SelectItem value="false">关闭</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">发送通道</label>
                <Input
                  value={settings.pushplus.channel}
                  onChange={(event) =>
                    setSettings((current) => ({
                      ...current,
                      pushplus: {
                        ...current.pushplus,
                        channel: event.target.value,
                      },
                    }))
                  }
                  placeholder="mail"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">通道参数</label>
              <Input
                value={settings.pushplus.channel_option}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    pushplus: {
                      ...current.pushplus,
                      channel_option: event.target.value,
                    },
                  }))
                }
                placeholder="例如邮箱地址、群组标识或其他附加参数"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">PushPlus Token</label>
              <Input
                value={settings.pushplus.token}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    pushplus: {
                      ...current.pushplus,
                      token: event.target.value,
                    },
                  }))
                }
                placeholder={settings.pushplus.has_token ? "留空则继续使用当前 Token" : "输入新的 PushPlus Token"}
              />
              <div className="text-xs text-muted-foreground">
                当前状态：{settings.pushplus.has_token ? `已配置（${settings.pushplus.token_preview ?? "已脱敏"}）` : "未配置"}
              </div>
            </div>

            <Button variant="outline" onClick={() => void testPushplus()} disabled={testingPushplus}>
              <Send className="size-4" />
              {testingPushplus ? "发送中..." : "测试 PushPlus 发送"}
            </Button>
          </CardContent>
        </Card>

        <Card className="soft-panel">
          <CardHeader>
            <CardTitle>默认分析提供方</CardTitle>
            <CardDescription>告警分析由 FastAPI 后端触发；这里决定默认走 DeepSeek 还是本地 OpenAI 兼容模型。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">默认提供方</label>
              <Select
                value={settings.default_provider}
                onValueChange={(value) =>
                  setSettings((current) => ({
                    ...current,
                    default_provider: value as AdminSystemSettings["default_provider"],
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="deepseek">DeepSeek</SelectItem>
                  <SelectItem value="local">本地模型</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Button variant="outline" onClick={() => void testDeepseek()} disabled={testingDeepseek}>
              <Sparkles className="size-4" />
              {testingDeepseek ? "测试中..." : "测试 DeepSeek 连通性"}
            </Button>

            {deepseekStatus ? (
              <div className="rounded-2xl border border-border/70 bg-background/80 p-4 text-sm">
                <div className="font-medium text-foreground">最近一次连通性测试</div>
                <div className="mt-2 text-muted-foreground">
                  提供方：{deepseekStatus.provider} / 模型：{deepseekStatus.model}
                </div>
                <div className="mt-1 text-muted-foreground">耗时：{deepseekStatus.latency_ms ?? "-"} ms</div>
                <div className="mt-3 leading-6 text-foreground">{deepseekStatus.message}</div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <ProviderCard
          title="DeepSeek"
          description="后端通过 OpenAI 兼容接口调用 DeepSeek。"
          settings={settings.deepseek}
          onChange={(key, value) => updateProviderField("deepseek", key, value)}
        />
        <ProviderCard
          title="本地模型"
          description="通常用于 Ollama 或其他本地 OpenAI 兼容服务。"
          settings={settings.local}
          onChange={(key, value) => updateProviderField("local", key, value)}
        />
      </section>
    </div>
  )
}

function ProviderCard({
  title,
  description,
  settings,
  onChange,
}: {
  title: string
  description: string
  settings: AdminSystemSettings["deepseek"]
  onChange: (key: "base_url" | "model" | "api_key", value: string) => void
}) {
  return (
    <Card className="soft-panel">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Base URL</label>
          <Input value={settings.base_url} onChange={(event) => onChange("base_url", event.target.value)} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">Model</label>
          <Input value={settings.model} onChange={(event) => onChange("model", event.target.value)} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-foreground">API Key</label>
          <Input
            type="password"
            value={settings.api_key}
            onChange={(event) => onChange("api_key", event.target.value)}
            placeholder="留空则继续使用当前已保存的 Key"
          />
        </div>
      </CardContent>
    </Card>
  )
}
