import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "@/App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("başlığı ve sunucu modunu gösterir", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ status: "ok", mode: "termux" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    render(<App />);

    expect(screen.getByRole("heading", { name: "FotoTakip çalışıyor" })).toBeInTheDocument();
    expect(await screen.findByText("termux")).toBeInTheDocument();
  });

  it("sunucuya ulaşılamazsa hata gösterir", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 503 })),
    );

    render(<App />);

    expect(await screen.findByText(/Sunucuya ulaşılamadı/)).toBeInTheDocument();
  });
});
