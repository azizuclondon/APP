// src/app/api/products/route.ts
import { NextResponse } from "next/server";

// Ensure this runs on the Node runtime and isn't statically cached.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Backend base URL: env in staging/prod; localhost in dev.
const BACKEND =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_BACKEND_URL ??
  "http://127.0.0.1:8000";

// GET → proxy to FastAPI GET /products (also useful to sanity-check the route)
export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/products`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    const data = await res.json().catch(() => ({}));
    // Log for debugging in your Next.js terminal:
    console.log("API: GET /api/products → backend status", res.status);

    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("API: GET /api/products error:", err?.message ?? err);
    return NextResponse.json(
      { detail: err?.message ?? "Proxy error (GET /api/products)" },
      { status: 500 }
    );
  }
}

// POST → proxy to FastAPI POST /products
export async function POST(req: Request) {
  console.log("API: POST /api/products hit");
  try {
    const body = await req.json(); // expects { brand, model }
    console.log("API: body =", body);

    const res = await fetch(`${BACKEND}/products`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json().catch(() => ({}));
    console.log("API: POST /api/products → backend status", res.status);

    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    console.error("API: POST /api/products error:", err?.message ?? err);
    return NextResponse.json(
      { detail: err?.message ?? "Proxy error (POST /api/products)" },
      { status: 500 }
    );
  }
}
