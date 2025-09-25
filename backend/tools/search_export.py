# -*- coding: utf-8 -*-
import os, argparse, json, csv
from tools.search_paginate import paginate_search

DEFAULT_FIELDS = [
    "document_id",
    "chunk_index",
    "section_path",
    "preview_clean",
    "page_from",
    "page_to",
    "score",
]

def pick(d: dict, fields):
    return {k: d.get(k) for k in fields}

def main():
    p = argparse.ArgumentParser(description="Export /search results with selected fields")
    p.add_argument("--text", required=True)
    p.add_argument("--top-k", type=int, default=3, dest="top_k")
    p.add_argument("--base-url", default=os.getenv("APP_API_BASE", "http://127.0.0.1:8000"))
    p.add_argument("--fields", nargs="*", default=DEFAULT_FIELDS, help="Fields to keep")
    p.add_argument("--out-jsonl", default=".\\tools\\out\\search_export.jsonl")
    p.add_argument("--out-csv",   default=".\\tools\\out\\search_export.csv")
    p.add_argument("--clean", action="store_true", help="Use clean previews")
    args = p.parse_args()

    rows = paginate_search(args.base_url, args.text, args.top_k, args.clean)
    os.makedirs(os.path.dirname(args.out_jsonl), exist_ok=True)

    # JSONL
    with open(args.out_jsonl, "w", encoding="utf-8") as jf:
        for r in rows:
            jf.write(json.dumps(pick(r, args.fields), ensure_ascii=False) + "\n")

    # CSV
    with open(args.out_csv, "w", newline="", encoding="utf-8") as cf:
        w = csv.DictWriter(cf, fieldnames=args.fields)
        w.writeheader()
        for r in rows:
            w.writerow(pick(r, args.fields))

    print(f"Wrote JSONL -> {args.out_jsonl}")
    print(f"Wrote CSV   -> {args.out_csv}")
    print(f"Rows exported: {len(rows)}")

if __name__ == "__main__":
    main()
