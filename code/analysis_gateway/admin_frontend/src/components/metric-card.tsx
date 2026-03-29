import type { ReactNode } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface MetricCardProps {
  title: string
  value: string
  hint: string
  icon: ReactNode
  tone?: "teal" | "green" | "orange" | "magenta"
}

const toneClasses = {
  teal: "bg-teal-50 text-teal-700 dark:bg-teal-500/15 dark:text-teal-200",
  green: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200",
  orange: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-200",
  magenta: "bg-fuchsia-50 text-fuchsia-700 dark:bg-fuchsia-500/15 dark:text-fuchsia-200",
}

export function MetricCard({ title, value, hint, icon, tone = "teal" }: MetricCardProps) {
  return (
    <Card className="soft-panel border-border/80">
      <CardHeader className="flex flex-row items-start justify-between gap-3 pb-3">
        <div>
          <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        </div>
        <div className={cn("flex size-10 items-center justify-center rounded-2xl", toneClasses[tone])}>{icon}</div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="text-3xl font-semibold tracking-tight text-foreground">{value}</div>
        <p className="text-sm leading-6 text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  )
}
