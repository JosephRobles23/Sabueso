import { getTranslations } from "next-intl/server";

import { InvestigationShell } from "./shell";

type PageProps = { params: Promise<{ id: string }> };

export default async function InvestigationPage({ params }: PageProps) {
  const { id } = await params;
  const t = await getTranslations("investigation");

  return (
    <InvestigationShell
      id={id}
      labels={{
        missionControl: t("missionControl"),
        investigationFloor: t("investigationFloor"),
        dossier: t("dossier"),
        loadingPlan: t("loadingPlan"),
        loadingFloor: t("loadingFloor"),
        loadingDossier: t("loadingDossier"),
        preparing: t("preparing"),
      }}
    />
  );
}
