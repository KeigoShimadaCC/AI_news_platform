import { NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

const execAsync = promisify(exec);

export async function POST(request: Request) {
  let body: { source?: string } = {};
  try {
    body = await request.json();
  } catch {
    // Empty body is fine - will ingest all
  }

  const source = body.source;
  const projectRoot = process.cwd();
  const venvPython = path.join(projectRoot, "venv", "bin", "python");

  // Sanitize source ID to prevent command injection
  if (source && !/^[a-zA-Z0-9_-]+$/.test(source)) {
    return NextResponse.json(
      { success: false, error: "Invalid source ID" },
      { status: 400 }
    );
  }

  const args = source
    ? `ingest --source ${source}`
    : "ingest --all";

  try {
    const { stdout, stderr } = await execAsync(
      `${venvPython} -m backend.pipeline.cli ${args}`,
      {
        cwd: projectRoot,
        timeout: 120_000, // 2 minute timeout
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
