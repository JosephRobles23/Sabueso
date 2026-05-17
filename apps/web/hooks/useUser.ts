"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { createClient } from "@/lib/supabase/client";

export function useUser() {
  const supabase = React.useMemo(() => createClient(), []);

  const query = useQuery({
    queryKey: ["supabase-user", Boolean(supabase)],
    queryFn: async () => {
      if (!supabase) return null;
      const { data, error } = await supabase.auth.getUser();
      if (error) throw error;
      return data.user;
    },
  });

  React.useEffect(() => {
    if (!supabase) return;
    const { data: subscription } = supabase.auth.onAuthStateChange(() => {
      query.refetch();
    });
    return () => subscription.subscription.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supabase]);

  return {
    user: query.data ?? null,
    isLoading: query.isLoading,
    refresh: query.refetch,
  };
}
