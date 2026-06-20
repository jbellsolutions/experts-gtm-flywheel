import { NextRequest, NextResponse } from "next/server";

// Simple shared-password gate (HTTP Basic Auth). Any username works; the
// password is DASH_PASSWORD (default "password1234"). Keeps the dashboard from
// being wide-open on its public URL. Static assets are excluded via `matcher`.
export function middleware(req: NextRequest) {
  const expected = process.env.DASH_PASSWORD || "password1234";
  const header = req.headers.get("authorization") || "";
  if (header.startsWith("Basic ")) {
    try {
      const decoded = atob(header.slice(6)); // "user:pass"
      const provided = decoded.slice(decoded.indexOf(":") + 1);
      if (provided === expected) return NextResponse.next();
    } catch {
      // fall through to 401
    }
  }
  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="AI Guy Dashboard"' },
  });
}

export const config = {
  // Gate everything except Next internals + favicon.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
