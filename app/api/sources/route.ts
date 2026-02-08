import { NextResponse } from "next/server";
import { getSources, getSourceById } from "@/lib/queries";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get("id");

  try {
    if (id) {
      const source = getSourceById(id);
      if (!source) {
        return NextResponse.json(
          { error: "Source not found" },
          { status: 404 }
        );
      }
      return NextResponse.json(source);
    }

    const sources = getSources();
    return NextResponse.json(sources, {
      headers: {
        "Cache-Control": "public, max-age=60, stale-while-revalidate=120",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to fetch sources", details: message },
      { status: 500 }
    );
  }
}
