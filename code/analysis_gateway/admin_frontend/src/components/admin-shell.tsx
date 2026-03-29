import { Menu, Search } from "lucide-react"
import { Link, Outlet, useLocation } from "react-router-dom"

import { AppSidebar } from "@/components/app-sidebar"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { cn } from "@/lib/utils"

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  "/admin": {
    title: "Monitoring Dashboard",
    subtitle: "Track instance health, alert delivery, and the items that need action.",
  },
  "/admin/alerts": {
    title: "Alerts Center",
    subtitle: "Filter, review, and export historical alert records.",
  },
}

function getPageMeta(pathname: string) {
  if (pathname.startsWith("/admin/instances/")) {
    return {
      title: "Instance Detail",
      subtitle: "Inspect one instance across capture trends, analyses, alerts, and errors.",
    }
  }

  return pageMeta[pathname] ?? pageMeta["/admin"]
}

export function AdminShell() {
  const location = useLocation()
  const meta = getPageMeta(location.pathname)

  return (
    <div className="app-shell lg:grid lg:grid-cols-[280px_minmax(0,1fr)]">
      <div className="hidden border-r border-sidebar-border/80 bg-sidebar lg:block">
        <AppSidebar />
      </div>

      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 border-b border-border/70 bg-background/92 backdrop-blur">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
            <div className="lg:hidden">
              <Sheet>
                <SheetTrigger render={<Button variant="outline" size="icon-sm" aria-label="Open navigation menu" />}>
                  <Menu className="size-4" />
                </SheetTrigger>
                <SheetContent side="left" className="w-[300px] p-0">
                  <SheetHeader className="sr-only">
                    <SheetTitle>Navigation menu</SheetTitle>
                  </SheetHeader>
                  <AppSidebar />
                </SheetContent>
              </Sheet>
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-foreground">{meta.title}</div>
              <div className="truncate text-xs text-muted-foreground">{meta.subtitle}</div>
            </div>

            <div className="hidden flex-1 items-center justify-center xl:flex">
              <div className="relative w-full max-w-md">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="toolbar-search pl-9" placeholder="Search instances, accounts, or alert titles" />
              </div>
            </div>

            <ThemeToggle />

            <div className="hidden items-center gap-3 rounded-full border border-border/70 bg-card px-3 py-2 md:flex">
              <div className="flex size-9 items-center justify-center rounded-full bg-primary/12 text-xs font-semibold text-primary">
                OPS
              </div>
              <div className="text-sm">
                <div className="font-medium text-foreground">Admin</div>
                <div className="text-xs text-muted-foreground">On-duty console</div>
              </div>
            </div>

            <Link to="/admin/alerts" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "hidden md:inline-flex")}>
              View alerts
            </Link>
          </div>
        </header>

        <main className="flex-1 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>

        <footer className="px-4 pb-6 pt-1 sm:px-6 lg:px-8">
          <div className="border-t border-border/70 pt-4 text-xs text-muted-foreground">
            First SPA iteration backed by the existing FastAPI admin APIs.
          </div>
        </footer>
      </div>
    </div>
  )
}
