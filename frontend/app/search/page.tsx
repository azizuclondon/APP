"use client";

import { useState } from "react";
import { searchApi, type SearchResultRow, type SearchResponse } from "@/lib/api";

// small helper: dedup by (document_id, chunk_index)
function dedup(rows: SearchResultRow[]): SearchResultRow[] {
  const seen = new Set<string>();
  const out: SearchResultRow[] = [];
  for (const r of rows) {
    const key = `${r.document_id}:${r.chunk_index}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(r);
    }
  }
  return out;
}

export default function SearchPage() {
  const [q, setQ] = useState("battery maintenance");
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState<SearchResultRow[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  async function runSearch(initial = true) {
    setLoading(true);
    setError(null);
    try {
      const resp: SearchResponse = await searchApi({
        text: q,
        top_k: 3,
        offset: initial ? 0 : (nextOffset ?? 0),
        clean_preview: true,
      });

      if (initial) {
        setRows(dedup(resp.results));
      } else {
        const merged = dedup([...rows, ...resp.results]);
        setRows(merged);
      }

      setNextOffset(resp.next_offset);
    } catch (e: any) {
      setError(e?.message ?? "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function copySnippet(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied("Copied!");
      setTimeout(() => setCopied(null), 1200);
    } catch {
      setCopied("Copy failed");
      setTimeout(() => setCopied(null), 1200);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Search</h1>
      <div className="text-sm text-gray-600">
        Results: {rows.length}{nextOffset === null && rows.length > 0 ? " (no more)" : ""}
      </div>

      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Type your query..."
        />
        <button
          className="px-4 py-2 rounded bg-black text-white disabled:opacity-50"
          onClick={() => runSearch(true)}
          disabled={loading}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {error && <div className="text-red-600 text-sm">{error}</div>}
      {copied && <div className="text-green-700 text-sm">{copied}</div>}

      <ul className="space-y-3">
        {rows.map((r, i) => {
          const snippet = (r.preview_clean || r.preview || "").trim() || "(no preview)";
          return (
            <li key={`${r.document_id}:${r.chunk_index}:${i}`} className="border rounded p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs text-gray-500">
                  doc {r.document_id} · chunk {r.chunk_index}
                  {typeof r.page_from === "number" ? (
                    <> · pages {r.page_from}{typeof r.page_to === "number" ? `–${r.page_to}` : ""}</>
                  ) : null}
                  {typeof r.score === "number" ? <> · score {r.score.toFixed(3)}</> : null}
                </div>
                <button
                  className="text-xs border px-2 py-1 rounded"
                  onClick={() => copySnippet(snippet)}
                  title="Copy snippet"
                >
                  Copy
                </button>
              </div>
              <div className="mt-1 whitespace-pre-line">
                {snippet}
              </div>
              {r.section_path ? (
                <div className="mt-1 text-xs text-gray-500">section: {r.section_path}</div>
              ) : null}
            </li>
          );
        })}
      </ul>

      <div className="pt-2">
        <button
          className="px-4 py-2 rounded border disabled:opacity-50"
          onClick={() => runSearch(false)}
          disabled={loading || nextOffset === null || rows.length === 0}
        >
          {nextOffset === null ? "No more results" : loading ? "Loading..." : "Load more"}
        </button>
      </div>
    </div>
  );
}
