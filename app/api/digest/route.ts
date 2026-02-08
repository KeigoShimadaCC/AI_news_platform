import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";
import { getDigest, getLatestDigest } from "@/lib/queries";

const execAsync = promisify(exec);

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

export async function POST(request: Request) {
  let body: { date?: string } = {};
  try {
    body = await request.json();
  } catch {
    // Empty body is fine - will generate for today
  }

  const dateParam = body.date;
  const projectRoot = process.cwd();
  const venvPython = path.join(projectRoot, "venv", "bin", "python");

  if (dateParam && !/^\d{4}-\d{2}-\d{2}$/.test(dateParam)) {
    return NextResponse.json(
      { success: false, error: "Invalid date format (use YYYY-MM-DD)" },
      { status: 400 }
    );
  }

  const args = dateParam ? `digest --date ${dateParam}` : "digest";

  try {
    const { stdout, stderr } = await execAsync(
      `${venvPython} -m backend.pipeline.cli ${args}`,
      {
        cwd: projectRoot,
        timeout: 120_000,
        env: { ...process.env, PYTHONPATH: projectRoot },
      }
    );

    return NextResponse.json({
      success: true,
      output: stdout,
      warnings: stderr || undefined,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
