import { NextRequest, NextResponse } from "next/server";

// Proxy for the browser extension. The extension authenticates with the same
// dashboard password (Basic auth, enforced by middleware), and this route
// forwards to prospect-api server-side with the X-API-Key — so the extension
// never needs the API key, and prospect-api can stay on the private network.
export async function POST(req: NextRequest) {
  const base = process.env.PROSPECT_API_URL;
  const key = process.env.PROSPECT_API_KEY;
  if (!base || !key) {
    return NextResponse.json({ error: "Prospecting API not configured." }, { status: 500 });
  }
  try {
    const body = await req.text();
    const r = await fetch(`${base.replace(/\/$/, "")}/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body,
      cache: "no-store",
    });
    const text = await r.text();
    return new NextResponse(text, {
      status: r.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e: any) {
    return NextResponse.json({ error: String(e?.message || e) }, { status: 502 });
  }
}
