import { NextRequest, NextResponse } from "next/server";

/**
 * Server-side proxy: avoids browser mixed-content (HTTPS Vercel → HTTP EC2).
 * Set IPL_GRAPHQL_BACKEND in Vercel (e.g. http://13.223.70.88:8000/graphql).
 */
export async function POST(req: NextRequest) {
  const backend = process.env.IPL_GRAPHQL_BACKEND?.trim();
  if (!backend) {
    return NextResponse.json(
      { errors: [{ message: "Server misconfigured: missing IPL_GRAPHQL_BACKEND" }] },
      { status: 500 }
    );
  }

  const body = await req.text();
  let upstream: Response;
  try {
    upstream = await fetch(backend, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body,
      cache: "no-store",
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "fetch failed";
    return NextResponse.json(
      { errors: [{ message: `Upstream unreachable: ${msg}` }] },
      { status: 502 }
    );
  }

  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/json",
    },
  });
}
