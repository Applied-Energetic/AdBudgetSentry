import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react"

import type { ThemeMode } from "@/lib/types"

interface ThemeContextValue {
  mode: ThemeMode
  resolvedMode: "light" | "dark"
  setMode: (mode: ThemeMode) => void
}

const STORAGE_KEY = "admin-theme"

const ThemeContext = createContext<ThemeContextValue | null>(null)

function getSystemMode() {
  if (typeof window === "undefined") {
    return "light" as const
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    if (typeof window === "undefined") {
      return "system"
    }

    const savedMode = window.localStorage.getItem(STORAGE_KEY)
    return savedMode === "light" || savedMode === "dark" || savedMode === "system"
      ? savedMode
      : "system"
  })
  const [systemMode, setSystemMode] = useState<"light" | "dark">(getSystemMode)

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
    const listener = (event: MediaQueryListEvent) => {
      setSystemMode(event.matches ? "dark" : "light")
    }

    setSystemMode(mediaQuery.matches ? "dark" : "light")
    mediaQuery.addEventListener("change", listener)

    return () => mediaQuery.removeEventListener("change", listener)
  }, [])

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, mode)
  }, [mode])

  const resolvedMode = mode === "system" ? systemMode : mode

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolvedMode === "dark")
  }, [resolvedMode])

  const value = useMemo(
    () => ({
      mode,
      resolvedMode,
      setMode,
    }),
    [mode, resolvedMode],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider")
  }

  return context
}
