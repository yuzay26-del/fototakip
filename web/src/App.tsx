import { Camera, CircleAlert, CircleCheck, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { getHealth, type HealthResponse } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthResponse }
  | { kind: "error"; message: string };

export default function App() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const check = useCallback(() => {
    setState({ kind: "loading" });
    getHealth()
      .then((health) => setState({ kind: "ok", health }))
      .catch((e: unknown) =>
        setState({ kind: "error", message: e instanceof Error ? e.message : "Bilinmeyen hata" }),
      );
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-background px-4 text-foreground">
      <div className="flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
        <Camera className="size-8" aria-hidden />
      </div>
      <h1 className="text-2xl font-semibold">FotoTakip çalışıyor</h1>

      <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
        {state.kind === "loading" && (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden /> Sunucu kontrol ediliyor…
          </>
        )}
        {state.kind === "ok" && (
          <>
            <CircleCheck className="size-4 text-emerald-600" aria-hidden />
            Sunucu ayakta · mod: <strong>{state.health.mode}</strong>
          </>
        )}
        {state.kind === "error" && (
          <>
            <CircleAlert className="size-4 text-destructive" aria-hidden /> {state.message}
          </>
        )}
      </p>

      <Button variant="outline" onClick={check} disabled={state.kind === "loading"}>
        Yeniden dene
      </Button>
    </main>
  );
}
