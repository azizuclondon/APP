# app/text_utils.py
import re
import unicodedata

# Common UTF-8/Win-1252 mojibake & symbols we want to fix
_MOJIBAKE_FIXES = {
    # dashes, quotes, bullets, ellipsis
    "â€“": "–",
    "â€”": "—",
    "â€˜": "‘",
    "â€™": "’",
    "â€œ": "“",
    "â€�": "”",
    "â€¦": "…",
    "â€¢": "•",

    # common stray prefix from bad decoding (removing this also fixes Â© -> ©, etc.)
    "Â": "",

    # explicit symbol fixes (covering cases where prefix removal isn’t enough)
    "Â©": "©",
    "Â®": "®",
    "â„¢": "™",
    "Â·": "·",
    "Ã—": "×",
    "âˆ’": "−",   # minus sign
    # sometimes ellipsis shows as a single bad unit
    "â¦": "…",
}

# Canonicalize to simpler ASCII where helpful for diffs/embeddings
_CANONICAL = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "–": "-",
    "—": "-",
    "•": "-",
}

# Zero-width & soft controls to remove
_STRIP_CHARS = [
    "\u200b",  # ZERO WIDTH SPACE
    "\ufeff",  # ZERO WIDTH NO-BREAK SPACE (BOM)
    "\u2060",  # WORD JOINER
    "\u00ad",  # SOFT HYPHEN
]

def normalize_text(s: str) -> str:
    if not s:
        return s

    # 1) Normalize unicode composition
    s = unicodedata.normalize("NFKC", s)

    # 2) Replace common mojibake sequences
    for bad, good in _MOJIBAKE_FIXES.items():
        s = s.replace(bad, good)

    # 3) Canonicalize punctuation (quotes/dashes/bullets)
    for bad, good in _CANONICAL.items():
        s = s.replace(bad, good)

    # 4) Non-breaking space -> normal space
    s = s.replace("\u00a0", " ")

    # 5) Strip zero-width / soft hyphen artifacts
    for ch in _STRIP_CHARS:
        s = s.replace(ch, "")

    # 6) Standardize newlines
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    # 7) Collapse excessive spaces per line, keep paragraph breaks
    lines = []
    for line in s.split("\n"):
        line = re.sub(r"[ ]{3,}", " ", line)  # collapse 3+ spaces (preserve double newlines)
        lines.append(line.rstrip())

    return "\n".join(lines).strip()
