import { Badge } from "@/components/ui/badge"
import { getSendStatusLabel, getSeverityLabel } from "@/lib/format"
import type { AlertSendStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

const severityClasses: Record<string, string> = {
  high: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/15 dark:text-rose-200",
  medium:
    "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-200",
  low: "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-500/30 dark:bg-slate-500/15 dark:text-slate-200",
}

const sendStatusClasses: Record<AlertSendStatus, string> = {
  sent: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-200",
  failed: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/15 dark:text-rose-200",
  skipped:
    "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-200",
}

export function AlertSeverityBadge({ severity }: { severity: string | null | undefined }) {
  const key = (severity || "").toLowerCase()
  return (
    <Badge variant="outline" className={cn("rounded-full px-2.5 py-0.5", severityClasses[key] || severityClasses.low)}>
      {getSeverityLabel(severity)}
    </Badge>
  )
}

export function AlertStatusBadge({ status }: { status: AlertSendStatus }) {
  return (
    <Badge variant="outline" className={cn("rounded-full px-2.5 py-0.5", sendStatusClasses[status])}>
      {getSendStatusLabel(status)}
    </Badge>
  )
}
