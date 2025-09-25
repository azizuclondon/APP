// src/app/products/page.tsx
// Server Component (no "use client"): fetch runs on the server ⇒ no CORS issues.

type Product = {
  id: number;
  brand: string;
  model: string;
};

const BACKEND = "http://127.0.0.1:8000"; // dev-only; we'll move to env var for staging

async function getProducts(): Promise<Product[]> {
  const res = await fetch(`${BACKEND}/products`, {
    cache: "no-store", // always show latest in dev
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch products: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export default async function ProductsPage() {
  const products = await getProducts();

  return (
    <main className="p-8 space-y-6">
      <h1 className="text-2xl font-semibold">Products</h1>

      {products.length === 0 ? (
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
        Fetched from <code>{BACKEND}/products</code> (SSR).
      </p>
    </main>
  );
}
