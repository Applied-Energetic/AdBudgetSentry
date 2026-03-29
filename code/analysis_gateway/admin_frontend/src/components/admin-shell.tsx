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
    title: "监控总览",
    subtitle: "统一查看实例健康度、告警投递和需要处理的异常波动。",
  },
  "/admin/alerts": {
    title: "告警中心",
    subtitle: "筛选、回看并导出历史告警记录。",
  },
}

function getPageMeta(pathname: string) {
  if (pathname.startsWith("/admin/instances/")) {
    return {
      title: "实例详情",
      subtitle: "查看单个实例的采样趋势、分析记录、告警和错误信息。",
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
          <div className="flex min-h-16 flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
            <div className="lg:hidden">
              <Sheet>
                <SheetTrigger render={<Button variant="outline" size="icon-sm" aria-label="打开导航菜单" />}>
                  <Menu className="size-4" />
                </SheetTrigger>
                <SheetContent side="left" className="w-[300px] p-0">
                  <SheetHeader className="sr-only">
                    <SheetTitle>导航菜单</SheetTitle>
                  </SheetHeader>
                  <AppSidebar />
                </SheetContent>
              </Sheet>
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-foreground">{meta.title}</div>
              <div className="truncate text-xs text-muted-foreground">{meta.subtitle}</div>
            </div>

            <div className="order-3 w-full xl:order-none xl:flex xl:flex-1 xl:items-center xl:justify-center">
              <div className="relative hidden w-full max-w-md xl:block">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="toolbar-search pl-9" placeholder="搜索实例、账户或告警标题" />
              </div>
            </div>

            <ThemeToggle />

            <div className="hidden items-center gap-3 rounded-full border border-border/70 bg-card px-3 py-2 md:flex">
              <div className="flex size-9 items-center justify-center rounded-full bg-primary/12 text-xs font-semibold text-primary">
                运维
              </div>
              <div className="text-sm">
                <div className="font-medium text-foreground">管理员</div>
                <div className="text-xs text-muted-foreground">监控工作台</div>
              </div>
            </div>

            <Link to="/admin/alerts" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "hidden md:inline-flex")}>
              查看告警
            </Link>
          </div>
        </header>

        <main className="flex-1 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>

        <footer className="px-4 pb-6 pt-1 sm:px-6 lg:px-8">
          <div className="border-t border-border/70 pt-4 text-xs text-muted-foreground">
            当前为第一版分离式管理后台，仍复用现有 FastAPI 监控接口。
          </div>
        </footer>
      </div>
    </div>
  )
}
