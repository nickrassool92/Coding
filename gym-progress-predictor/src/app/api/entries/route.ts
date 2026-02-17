import { NextResponse } from "next/server";

// API routes for future backend integration
// Currently the app uses localStorage for data persistence
// These routes serve as the API contract for when a backend database is added

export async function GET() {
  return NextResponse.json({
    message: "Entries are currently stored client-side in localStorage",
    hint: "Connect a database (e.g., Supabase, PlanetScale) to enable server-side persistence",
  });
}

export async function POST(request: Request) {
  const body = await request.json();
  // TODO: Save to database
  return NextResponse.json({
    message: "Entry received",
    entry: body,
    hint: "Implement database save logic here",
  });
}
