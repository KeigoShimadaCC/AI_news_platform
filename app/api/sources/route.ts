import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";
import { getSources, getSourceById } from "@/lib/queries";

const execAsync = promisify(exec);

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

export async function PATCH(request: Request) {
  let body: { id?: string; enabled?: boolean } = {};
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { success: false, error: "Invalid JSON body" },
      { status: 400 }
    );
  }

  const { id: sourceId, enabled } = body;
  if (sourceId == null || typeof enabled !== "boolean") {
    return NextResponse.json(
      { success: false, error: "Body must include id (string) and enabled (boolean)" },
      { status: 400 }
    );
  }

  if (!/^[a-zA-Z0-9_-]+$/.test(sourceId)) {
    return NextResponse.json(
      { success: false, error: "Invalid source ID" },
      { status: 400 }
    );
  }

  const projectRoot = process.cwd();
  const venvPython = path.join(projectRoot, "venv", "bin", "python");
  const enabledStr = enabled ? "true" : "false";

  try {
    const { stdout, stderr } = await execAsync(
      `${venvPython} -m backend.pipeline.cli source --id ${sourceId} --enabled ${enabledStr}`,
      {
        cwd: projectRoot,
        timeout: 10_000,
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
