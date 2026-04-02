import { Expand, Minimize2 } from "lucide-react"
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { formatDecimal } from "@/lib/format"

export interface TrendChartPoint {
  timestamp: number
  label: string
  value: number
  referenceValue?: number | null
}

interface TrendChartCardProps {
  title: string
  description: string
  data: TrendChartPoint[]
  color: string
  emptyText: string
  valueLabel: string
  referenceLabel?: string
  referenceColor?: string
}

export function TrendChartCard({
  title,
  description,
  data,
  color,
  emptyText,
  valueLabel,
  referenceLabel,
  referenceColor,
}: TrendChartCardProps) {
  return (
    <Card className="soft-panel">
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="space-y-1">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <Dialog>
          <DialogTrigger
            render={
              <Button variant="outline" size="sm" className="shrink-0 rounded-full">
                <Expand className="size-4" />
                <span className="hidden sm:inline">全屏</span>
              </Button>
            }
          />
          <DialogContent className="max-w-[min(100vw-1rem,1080px)] p-0 sm:max-w-[min(100vw-2rem,1080px)]">
            <DialogHeader className="border-b border-border/80 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <DialogTitle>{title}</DialogTitle>
                  <DialogDescription>{description}</DialogDescription>
                </div>
                <DialogClose render={<Button variant="ghost" size="icon-sm" className="rounded-full" />}>
                  <Minimize2 className="size-4" />
                </DialogClose>
              </div>
            </DialogHeader>
            <div className="h-[72vh] px-4 pb-4 pt-2 sm:px-6 sm:pb-6">
              <TrendChartCanvas
                data={data}
                color={color}
                emptyText={emptyText}
                valueLabel={valueLabel}
                referenceLabel={referenceLabel}
                referenceColor={referenceColor}
              />
            </div>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent className="h-[320px] pt-2">
        <TrendChartCanvas
          data={data}
          color={color}
          emptyText={emptyText}
          valueLabel={valueLabel}
          referenceLabel={referenceLabel}
          referenceColor={referenceColor}
        />
      </CardContent>
    </Card>
  )
}

function TrendChartCanvas({
  data,
  color,
  emptyText,
  valueLabel,
  referenceLabel,
  referenceColor,
}: {
  data: TrendChartPoint[]
  color: string
  emptyText: string
  valueLabel: string
  referenceLabel?: string
  referenceColor?: string
}) {
  if (data.length < 2) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-border/80 text-sm text-muted-foreground">
        {emptyText}
      </div>
    )
  }

  const gradientId = `trend-gradient-${color.replace(/[^a-z0-9]/gi, "")}`

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={10} minTickGap={24} />
        <YAxis tickLine={false} axisLine={false} width={62} tickFormatter={(value: number) => formatDecimal(value)} />
        <Tooltip
          formatter={(value, name) => {
            const label = String(name || valueLabel)
            return [`${formatDecimal(Number(value))} ${valueLabel}`, label]
          }}
          labelFormatter={(label) => `时间：${String(label ?? "-")}`}
          cursor={{ stroke: color, strokeOpacity: 0.25, strokeDasharray: "4 4" }}
          contentStyle={{
            borderRadius: 18,
            border: "1px solid var(--color-border)",
            background: "color-mix(in srgb, var(--color-card) 96%, white)",
            boxShadow: "0 16px 40px rgba(15, 23, 42, 0.08)",
          }}
        />
        <Area
          type="monotone"
          dataKey="value"
          name={valueLabel}
          stroke={color}
          fill={`url(#${gradientId})`}
          strokeWidth={2.5}
          activeDot={{ r: 4, strokeWidth: 0, fill: color }}
          isAnimationActive={false}
        />
        {referenceLabel ? (
          <Line
            type="monotone"
            dataKey="referenceValue"
            name={referenceLabel}
            stroke={referenceColor ?? "var(--color-muted-foreground)"}
            strokeWidth={2}
            strokeDasharray="6 6"
            dot={false}
            activeDot={{ r: 3 }}
            connectNulls
            isAnimationActive={false}
          />
        ) : null}
      </AreaChart>
    </ResponsiveContainer>
  )
}
