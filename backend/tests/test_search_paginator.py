import httpx
from tools.search_paginate import paginate_search

class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)
    def json(self):
        return self._payload

def test_paginate_dedup(monkeypatch):
    # Page 1 returns 2 rows; second will be duplicated on page 2
    page1 = {
        "results": [
            {"document_id": 1, "chunk_index": 10, "preview_clean": "A"},
            {"document_id": 1, "chunk_index": 11, "preview_clean": "B DUP"},
        ],
        "next_offset": 2,
    }
    # Page 2 returns the duplicate + a new one
    page2 = {
        "results": [
            {"document_id": 1, "chunk_index": 11, "preview_clean": "B DUP again"},
            {"document_id": 1, "chunk_index": 12, "preview_clean": "C"},
        ],
        "next_offset": None,
    }

    calls = {"count": 0}
    def fake_post(url, json=None, timeout=None):
        if calls["count"] == 0:
            assert json["offset"] == 0
            calls["count"] += 1
            return FakeResponse(page1)
        elif calls["count"] == 1:
            assert json["offset"] == 2
            calls["count"] += 1
            return FakeResponse(page2)
        else:
            raise AssertionError("Called more than twice")

    # patch httpx.post to our fake
    monkeypatch.setattr(httpx, "post", fake_post)

    rows = paginate_search("http://dummy", text="q", top_k=3, clean=True)

    # Dedup by (document_id, chunk_index) should reduce to 3 uniques: 10,11,12
    assert len(rows) == 3
    assert {r["chunk_index"] for r in rows} == {10, 11, 12}
    assert calls["count"] == 2
