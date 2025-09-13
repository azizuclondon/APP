// src/app/products/new/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function NewProductPage() {
  const router = useRouter();
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);

    try {
      // Same-origin call to your Next.js API proxy
      const res = await fetch("/api/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brand, model }),
      });

      if (res.status === 201) {
        // success → go back to list
        router.push("/products");
        router.refresh();
        return;
      }

      const data = await res.json().catch(() => ({}));
      setError(data?.detail ?? `Failed: ${res.status} ${res.statusText}`);
    } catch (err: any) {
      setError(err?.message ?? "Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="p-8 max-w-md space-y-6">
      <h1 className="text-2xl font-semibold">New Product</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm mb-1">Brand</label>
          <input
            className="w-full border rounded-lg p-2"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            placeholder="e.g., DJI"
            required
            maxLength={255}
          />
        </div>

        <div>
          <label className="block text-sm mb-1">Model</label>
          <input
            className="w-full border rounded-lg p-2"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="e.g., Mini 4 Pro"
            required
            maxLength={255}
          />
        </div>

        <button
          type="submit"
          disabled={busy}
          className="px-4 py-2 rounded-xl border shadow-sm"
        >
          {busy ? "Saving..." : "Create"}
        </button>

        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </form>

      <p className="text-xs opacity-60">
        Submits to <code>POST /api/products</code> → proxies to FastAPI.
      </p>
    </main>
  );
}
