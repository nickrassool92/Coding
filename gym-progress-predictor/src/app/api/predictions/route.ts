import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const body = await request.json();
  // TODO: Run server-side prediction model
  return NextResponse.json({
    message: "Predictions are currently generated client-side",
    entriesReceived: body?.entries?.length || 0,
    hint: "Integrate an ML model or AI API for more advanced predictions",
  });
}
