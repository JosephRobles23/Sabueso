import type { ComposedInvestigationState } from "@/lib/mockInvestigationState"
import { KEIKO_MOCK_STATE } from "./keiko-fujimori"

const DEMO_MOCKS: Record<string, ComposedInvestigationState> = {
  "demo-keiko-fujimori": KEIKO_MOCK_STATE,
}

export function getDemoMockState(id: string): ComposedInvestigationState | null {
  return DEMO_MOCKS[id] ?? null
}
