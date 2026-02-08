import { NextResponse } from "next/server";
import { searchItems } from "@/lib/queries";
import type { SearchFilters } from "@/lib/types";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);

  const query = searchParams.get("q") || "";
  const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
  const limit = Math.min(100, Math.max(1, parseInt(searchParams.get("limit") || "50", 10)));

  const filters: SearchFilters = {};
  const category = searchParams.get("category");
  const source = searchParams.get("source");
  const lang = searchParams.get("lang");
  const dateFrom = searchParams.get("dateFrom");
  const dateTo = searchParams.get("dateTo");
  const sortBy = searchParams.get("sortBy") as SearchFilters["sortBy"];

  if (category) filters.category = category;
  if (source) filters.source = source;
  if (lang) filters.lang = lang;
  if (dateFrom) filters.dateFrom = dateFrom;
  if (dateTo) filters.dateTo = dateTo;
  if (sortBy && ["score", "date", "relevance"].includes(sortBy)) {
    filters.sortBy = sortBy;
  }

  try {
    const result = searchItems(query, filters, page, limit);

    return NextResponse.json(result, {
      headers: {
        "Cache-Control": "public, max-age=60, stale-while-revalidate=120",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Search failed", details: message },
      { status: 500 }
    );
  }
}
