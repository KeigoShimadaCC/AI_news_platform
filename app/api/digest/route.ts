import { NextResponse } from "next/server";
import { getDigest, getLatestDigest } from "@/lib/queries";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date");

  try {
    const digest = date ? getDigest(date) : getLatestDigest();

    return NextResponse.json(digest, {
      headers: {
        "Cache-Control": "public, max-age=300, stale-while-revalidate=600",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to fetch digest", details: message },
      { status: 500 }
    );
  }
}
