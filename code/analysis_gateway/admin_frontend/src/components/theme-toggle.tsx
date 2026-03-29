import { LaptopMinimal, MoonStar, SunMedium } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useTheme } from "@/lib/theme"
import type { ThemeMode } from "@/lib/types"

const options: Array<{ value: ThemeMode; label: string; icon: typeof LaptopMinimal }> = [
  { value: "system", label: "跟随系统", icon: LaptopMinimal },
  { value: "light", label: "浅色", icon: SunMedium },
  { value: "dark", label: "深色", icon: MoonStar },
]

export function ThemeToggle() {
  const { mode, setMode } = useTheme()

  return (
    <div className="flex items-center gap-1 rounded-full border border-border/70 bg-card/90 p-1">
      {options.map((option) => {
        const Icon = option.icon

        return (
          <Button
            key={option.value}
            variant={mode === option.value ? "default" : "ghost"}
            size="sm"
            onClick={() => setMode(option.value)}
            className="rounded-full"
          >
            <Icon className="size-4" />
            <span className="hidden md:inline">{option.label}</span>
          </Button>
        )
      })}
    </div>
  )
}
