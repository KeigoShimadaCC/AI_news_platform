import { NextResponse } from "next/server";
import { getKeywordSettings, setKeywordSettings } from "@/lib/queries";
import type { KeywordSettings } from "@/lib/types";

export async function GET() {
  try {
    const settings = getKeywordSettings();
    return NextResponse.json(settings, {
      headers: {
        "Cache-Control": "private, max-age=0",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to load keyword settings", details: message },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request) {
  let body: Partial<KeywordSettings> = {};
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { ok: false, error: "Invalid JSON body" },
      { status: 400 }
    );
  }

  const settings: KeywordSettings = {
    filterEnabled: typeof body.filterEnabled === "boolean" ? body.filterEnabled : false,
    globalKeywords: Array.isArray(body.globalKeywords)
      ? body.globalKeywords.filter((k) => typeof k === "string")
      : [],
    sourceKeywords:
      body.sourceKeywords && typeof body.sourceKeywords === "object"
        ? Object.fromEntries(
            Object.entries(body.sourceKeywords).filter(
              ([_, arr]) => Array.isArray(arr) && arr.every((k) => typeof k === "string")
            )
          )
        : {},
  };

  const result = setKeywordSettings(settings);
  if (!result.ok) {
    return NextResponse.json(
      { ok: false, error: result.error },
      { status: 500 }
    );
  }
  return NextResponse.json({ ok: true, settings });
}
