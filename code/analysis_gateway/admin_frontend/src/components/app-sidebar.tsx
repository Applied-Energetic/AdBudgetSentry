import { AlertTriangle, LayoutDashboard, Server } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useLocation } from "react-router-dom"

import { HealthBadge } from "@/components/health-badge"
import { Badge } from "@/components/ui/badge"
import { adminApi } from "@/lib/api"
import { formatAccountIdentity } from "@/lib/format"
import type { AdminInstanceSummary } from "@/lib/types"
import { cn } from "@/lib/utils"

const navigationItems = [
  { title: "Overview", href: "/admin", icon: LayoutDashboard, exact: true },
  { title: "Alerts", href: "/admin/alerts", icon: AlertTriangle },
]

export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation()
  const [instances, setInstances] = useState<AdminInstanceSummary[]>([])

  useEffect(() => {
    void adminApi.getInstances().then((items) => setInstances(items.slice(0, 6))).catch(() => setInstances([]))
  }, [])

  return (
    <aside className="flex h-full w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold tracking-[0.22em] text-muted-foreground">ADBUDGET</div>
            <div className="mt-1 text-lg font-semibold">Admin Console</div>
          </div>
          <Badge className="rounded-full bg-primary px-2.5 py-0.5 text-primary-foreground">v1</Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">A clean control surface for monitoring instances, alerts, and spend anomalies.</p>
      </div>

      <nav className="space-y-1 px-3 pb-4">
        {navigationItems.map((item) => {
          const isActive = item.exact ? location.pathname === item.href : location.pathname.startsWith(item.href)
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              to={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              )}
            >
              <Icon className="size-4" />
              <span>{item.title}</span>
            </Link>
          )
        })}
      </nav>

      <div className="border-t border-sidebar-border px-5 pt-4">
        <div className="mb-3 text-[11px] font-semibold tracking-[0.18em] text-muted-foreground">Priority instances</div>
        <div className="space-y-2">
          {instances.length === 0 ? (
            <div className="rounded-2xl border border-sidebar-border/80 bg-background/70 px-4 py-3 text-sm text-muted-foreground">
              No instances yet
            </div>
          ) : null}
          {instances.map((instance) => {
            const href = `/admin/instances/${instance.instance_id}`
            const isActive = location.pathname === href
            const displayName = instance.alias || formatAccountIdentity(instance.account_name, instance.account_id)

            return (
              <Link
                key={instance.instance_id}
                to={href}
                onClick={onNavigate}
                className={cn(
                  "block rounded-2xl border border-transparent bg-background/70 px-4 py-3 transition-colors",
                  isActive ? "border-sidebar-border bg-sidebar-accent" : "hover:border-sidebar-border hover:bg-sidebar-accent/70",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Server className="size-4 text-muted-foreground" />
                    <span className="line-clamp-1 text-sm font-medium">{displayName}</span>
                  </div>
                  <HealthBadge status={instance.health_status} />
                </div>
                <div className="mt-2 line-clamp-1 text-xs text-muted-foreground">
                  {instance.remarks || formatAccountIdentity(instance.account_name, instance.account_id)}
                </div>
              </Link>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
