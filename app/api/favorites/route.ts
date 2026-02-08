import { NextResponse } from "next/server";
import {
  getFavorites,
  addFavorite,
  removeFavorite,
  getItem,
} from "@/lib/queries";

export async function GET() {
  try {
    const favorites = getFavorites();
    return NextResponse.json(favorites, {
      headers: {
        "Cache-Control": "private, max-age=10",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { error: "Failed to fetch favorites", details: message },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  let body: { item_id?: string } = {};
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { success: false, error: "Invalid JSON body" },
      { status: 400 }
    );
  }

  const itemId = body.item_id;
  if (!itemId || typeof itemId !== "string") {
    return NextResponse.json(
      { success: false, error: "Body must include item_id (string)" },
      { status: 400 }
    );
  }

  const item = getItem(itemId);
  if (!item) {
    return NextResponse.json(
      { success: false, error: "Item not found" },
      { status: 404 }
    );
  }

  const result = addFavorite(itemId);
  if (!result.ok) {
    return NextResponse.json(
      { success: false, error: result.error },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, item_id: itemId });
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const itemId = searchParams.get("item_id");

  if (!itemId) {
    return NextResponse.json(
      { success: false, error: "Query item_id is required" },
      { status: 400 }
    );
  }

  const result = removeFavorite(itemId);
  if (!result.ok) {
    return NextResponse.json(
      { success: false, error: result.error },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}
