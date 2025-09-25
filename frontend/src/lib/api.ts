export type SearchRequest = {
  text: string;
  top_k?: number;
  offset?: number;
  clean_preview?: boolean;
};

export type SearchResultRow = {
  document_id: number;
  chunk_index: number;
  section_path?: string | null;
  preview_clean?: string | null;
  preview?: string | null;
  page_from?: number | null;
  page_to?: number | null;
  score?: number | null;
};

export type SearchResponse = {
  query: string;
  top_k: number;
  offset: number;
  next_offset: number | null;
  results: SearchResultRow[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export async function searchApi(payload: SearchRequest): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Search failed: ${res.status} ${res.statusText} ${text}`);
  }
  return res.json();
}
