import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    message: "Achievements are currently managed client-side",
    hint: "Add server-side achievement tracking for multi-device sync",
  });
}
