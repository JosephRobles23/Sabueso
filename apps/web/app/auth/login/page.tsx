"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState<"google" | "magic" | null>(null);
  const supabase = createClient();
  const configured = supabase !== null;

  async function signInWithGoogle() {
    if (!supabase) return;
    setPending("google");
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback?next=/app` },
    });
    if (error) toast.error(error.message);
    setPending(null);
  }

  async function sendMagicLink(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || !email) return;
    setPending("magic");
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=/app` },
    });
    if (error) {
      toast.error(error.message);
    } else {
      toast.success(t("magicSent"));
    }
    setPending(null);
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>{t("loginTitle")}</CardTitle>
          <CardDescription>{t("loginSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {!configured && (
            <p className="rounded-[var(--radius-md)] bg-[var(--color-paper)] px-3 py-2 text-xs text-[var(--color-text-paper)]">
              Supabase no está configurado. Definí <code>NEXT_PUBLIC_SUPABASE_URL</code> y{" "}
              <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> en <code>.env</code>.
            </p>
          )}
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={signInWithGoogle}
            disabled={pending !== null || !configured}
          >
            {t("continueWithGoogle")}
          </Button>

          <div className="flex items-center gap-3 text-xs uppercase text-[var(--color-text-muted)]">
            <span className="h-px flex-1 bg-[var(--color-border-default)]" />
            <span>o</span>
            <span className="h-px flex-1 bg-[var(--color-border-default)]" />
          </div>

          <form className="space-y-3" onSubmit={sendMagicLink}>
            <div className="space-y-1.5">
              <Label htmlFor="email">{t("email")}</Label>
              <Input
                id="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                required
                placeholder={t("emailPlaceholder")}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <Button type="submit" className="w-full" disabled={pending !== null || !configured}>
              {t("sendMagicLink")}
            </Button>
          </form>

          <p className="text-center text-xs text-[var(--color-text-muted)]">
            {t("anonymousHint")}
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
