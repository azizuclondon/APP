// src/app/api/products/route.ts
import { NextResponse } from "next/server";

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  process.env.BACKEND_URL ??
  "http://127.0.0.1:8000";

// GET → proxy to FastAPI GET /products
export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/products`, { cache: "no-store" });
    const data = await res.json().catch(() => []);
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Proxy error (GET /api/products)";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}

// POST → proxy to FastAPI POST /products
export async function POST(req: Request) {
  try {
    const body: unknown = await req.json();

    // Narrow unknown to expected shape
    const payload =
      typeof body === "object" && body !== null
        ? (body as { brand?: string; model?: string })
        : {};

    const res = await fetch(`${BACKEND}/products`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Proxy error (POST /api/products)";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
