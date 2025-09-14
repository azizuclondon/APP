// src/app/products/page.tsx

export const dynamic = "force-dynamic"; // ensure this runs at request time on Vercel

type Product = {
  id: number;
  brand: string;
  model: string;
};

function getBaseUrl() {
  // Prefer an explicit site URL if you add one later
  if (process.env.NEXT_PUBLIC_SITE_URL) {
    return process.env.NEXT_PUBLIC_SITE_URL;
  }
  // Vercel provides VERCEL_URL without protocol (e.g., app-xxxx.vercel.app)
  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`;
  }
  // Local dev fallback
  return "http://localhost:3006";
}

// Call our own Next.js API route (which proxies to FastAPI on Render)
async function getProducts(): Promise<Product[]> {
  const base = getBaseUrl();
  const res = await fetch(`${base}/api/products`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`/api/products failed: ${res.status} ${res.statusText} ${body}`);
  }
  return res.json();
}

export default async function ProductsPage() {
  let products: Product[] = [];
  let error: string | null = null;

  try {
    products = await getProducts();
  } catch (e: unknown) {
    error = e instanceof Error ? e.message : "Unknown error fetching products.";
  }

  return (
    <main className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Products</h1>
        <a href="/products/new" className="px-3 py-2 rounded-xl border shadow-sm text-sm">
          + New
        </a>
      </div>

      {error ? (
        <p className="text-sm text-red-600">Error: {error}</p>
      ) : products.length === 0 ? (
        <p className="text-sm opacity-70">No products yet.</p>
      ) : (
        <div className="overflow-x-auto border rounded-xl">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-gray-100">
                <th className="text-left p-3">ID</th>
                <th className="text-left p-3">Brand</th>
                <th className="text-left p-3">Model</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="p-3">{p.id}</td>
                  <td className="p-3">{p.brand}</td>
                  <td className="p-3">{p.model}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs opacity-60">
        Fetched via SSR from <code>/api/products</code> (proxy to your Render backend).
      </p>
    </main>
  );
}
