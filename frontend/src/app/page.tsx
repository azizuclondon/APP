async function getPing() {
const res = await fetch("http://127.0.0.1:8000/ping", { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return res.json() as Promise<{ message: string }>;
}


export default async function Home() {
  const data = await getPing(); // waits on the server, not the browser
  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold">Frontend ↔ Backend OK ✅</h1>
        <p className="text-sm">Backend says: <span className="font-mono">{data.message}</span></p>
      </div>
    </main>
  );
}
