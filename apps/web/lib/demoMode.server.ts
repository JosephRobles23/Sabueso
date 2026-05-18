import { cookies } from "next/headers"

import { DEMO_MODE_COOKIE, normalizeDemoMode, type DemoMode } from "./demoMode"

export async function getDemoMode(): Promise<DemoMode> {
  const store = await cookies()
  return normalizeDemoMode(store.get(DEMO_MODE_COOKIE)?.value)
}
