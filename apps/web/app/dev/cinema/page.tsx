import { InvestigationShell } from "@/app/(app)/i/[id]/shell";
import { MOCK_INVESTIGATION_STATE } from "@/lib/mockInvestigationState";

export const dynamic = "force-static";

const LABELS = {
  missionControl: "Mission Control",
  investigationFloor: "Investigation Floor",
  dossier: "Dossier",
  loadingPlan: "El equipo se está armando.",
  loadingFloor: "Esperando los primeros hallazgos.",
  loadingDossier: "El dossier se va a llenar en tiempo real.",
  preparing: "Preparando investigación...",
};

export default function DevCinemaPage() {
  return (
    <InvestigationShell
      id={MOCK_INVESTIGATION_STATE.id}
      labels={LABELS}
      state={MOCK_INVESTIGATION_STATE}
    />
  );
}
