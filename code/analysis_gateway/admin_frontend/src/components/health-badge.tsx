import { Badge } from "@/components/ui/badge"
import { getHealthLabel } from "@/lib/format"
import type { HealthStatus } from "@/lib/types"
import { cn } from "@/lib/utils"

const toneClasses: Record<HealthStatus, string> = {
  green:
    "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-200",
  yellow:
    "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-200",
  red:
    "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/15 dark:text-rose-200",
}

export function HealthBadge({ status }: { status: HealthStatus }) {
  return (
    <Badge variant="outline" className={cn("rounded-full px-2.5 py-0.5", toneClasses[status])}>
      {getHealthLabel(status)}
    </Badge>
  )
}
