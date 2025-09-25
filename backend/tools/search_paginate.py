# -*- coding: utf-8 -*-
import os, argparse, sys, csv
import httpx

def paginate_search(base_url, text, top_k=3, clean=False):
    """
    Call POST {base_url}/search repeatedly following next_offset.
    Returns a list of unique rows (dedup by document_id + chunk_index).
    """
    url = f"{base_url.rstrip('/')}/search"
    offset = 0
    seen = set()
    all_rows = []

    while True:
        payload = {
            "text": text,
            "top_k": top_k,
            "offset": offset,
            "clean_preview": bool(clean),
        }
        r = httpx.post(url, json=payload, timeout=30.0)
        r.raise_for_status()
        data = r.json()

        results = data.get("results", [])
        next_offset = data.get("next_offset", None)

        for row in results:
            key = (row.get("document_id"), row.get("chunk_index"))
            if key not in seen:
                seen.add(key)
                all_rows.append(row)

        print(f"Fetched {len(results)} rows (this page). next_offset={next_offset}")

        if next_offset is None:
            break
        offset = next_offset

    return all_rows

def main():
    parser = argparse.ArgumentParser(description="Paginate /search results")
    parser.add_argument("--text", required=True, help="Query text")
    parser.add_argument("--top-k", type=int, default=3, dest="top_k")
    parser.add_argument("--base-url", default=os.getenv("APP_API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--clean", action="store_true", help="Use clean previews")
    parser.add_argument("--csv", help="Optional path to write results as CSV")
    args = parser.parse_args()

    rows = paginate_search(args.base_url, args.text, args.top_k, args.clean)

    print("\n=== SUMMARY ===")
    print(f"Total unique rows (by doc_id+chunk_index): {len(rows)}")
    print("Showing first 5 previews:")
    for i, row in enumerate(rows[:5], 1):
        pv = (row.get("preview_clean") or row.get("preview") or "").replace("\\n", " ")
        dots = "..." if len(pv) > 140 else ""
        print(f"{i:>2}. [doc {row.get('document_id')}] {pv[:140]}{dots}")

    if args.csv:
        out_dir = os.path.dirname(args.csv)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        fieldnames = [
            "document_id","chunk_index","section_path","score",
            "preview_clean","preview","page_from","page_to"
        ]
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in rows:
                w.writerow({
                    "document_id": row.get("document_id"),
                    "chunk_index": row.get("chunk_index"),
                    "section_path": row.get("section_path"),
                    "score": row.get("score"),
                    "preview_clean": row.get("preview_clean"),
                    "preview": row.get("preview"),
                    "page_from": row.get("page_from"),
                    "page_to": row.get("page_to"),
                })
        print(f"\nSaved CSV -> {args.csv}")

if __name__ == "__main__":
    main()
