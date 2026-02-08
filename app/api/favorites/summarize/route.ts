import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

const execAsync = promisify(exec);

/** POST: run Python summarize-favorites (optionally for one item_id). */
export async function POST(request: Request) {
  let body: { item_id?: string } = {};
  try {
    body = await request.json();
  } catch {
    // Empty body = summarize all missing
  }

  const projectRoot = process.cwd();
  const venvPython = path.join(projectRoot, "venv", "bin", "python");
  const args = body.item_id
    ? `summarize-favorites --item-id ${body.item_id}`
    : "summarize-favorites";

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
