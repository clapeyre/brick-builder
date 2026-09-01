import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@sinclair/typebox";
import { defineTool, type ToolDefinition, type CreateAgentSessionOptions } from "@earendil-works/pi-coding-agent";

export type DomainOperation = "catalog" | "validate" | "analyze" | "compile" | "demo-generate";
export type RunnerOptions = { runRoot: string; python?: string; repositoryRoot?: string; signal?: AbortSignal };
export type CommandResult = { valid: boolean; [key: string]: unknown };

const operations = ["catalog", "validate", "analyze", "compile", "demo-generate"] as const;
const here = dirname(fileURLToPath(import.meta.url));
const defaultRepo = resolve(here, "../..");

function contained(root: string, candidate: string): string {
  const base = resolve(root), path = resolve(candidate);
  const rel = relative(base, path);
  if (rel === "" || rel === ".." || rel.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`) || isAbsolute(rel)) {
    throw new Error("path must remain inside the caller-provided run root");
  }
  return path;
}

async function invoke(args: string[], options: RunnerOptions): Promise<CommandResult> {
  const root = resolve(options.runRoot);
  await mkdir(root, { recursive: true });
  const python = options.python ?? (process.platform === "win32" ? "python" : "python3");
  return await new Promise((resolvePromise, reject) => {
    const child = spawn(python, ["-m", "brick_builder.cli", ...args], {
      cwd: options.repositoryRoot ?? defaultRepo,
      stdio: ["ignore", "pipe", "pipe"],
      shell: false,
      signal: options.signal,
    });
    let stdout = "", stderr = "";
    child.stdout.on("data", (data) => { stdout += data; });
    child.stderr.on("data", (data) => { stderr += data; });
    child.on("error", (error) => reject(error));
    child.on("close", (code) => {
      try {
        const result = JSON.parse(stdout.trim()) as CommandResult;
        if (stderr) result.stderr = stderr;
        result.exit_code = code ?? 1;
        resolvePromise(result);
      } catch {
        reject(new Error(`Brick Builder CLI returned malformed output (exit ${code}): ${stderr || stdout}`));
      }
    });
  });
}

export class BrickBuilderAdapter {
  readonly runRoot: string;
  constructor(private readonly options: RunnerOptions) { this.runRoot = resolve(options.runRoot); }

  async catalog(): Promise<CommandResult> {
    return invoke(["catalog"], this.options);
  }
  async validate(model: Record<string, unknown>): Promise<CommandResult> {
    const path = contained(this.runRoot, resolve(this.runRoot, "input-model.json"));
    await writeFile(path, JSON.stringify(model, null, 2) + "\n", "utf8");
    return invoke(["validate", path], this.options);
  }
  async analyze(model: Record<string, unknown>): Promise<CommandResult> {
    const path = contained(this.runRoot, resolve(this.runRoot, "input-model.json"));
    await writeFile(path, JSON.stringify(model, null, 2) + "\n", "utf8");
    return invoke(["analyze", path], this.options);
  }
  async compile(model: Record<string, unknown>): Promise<CommandResult> {
    const modelPath = contained(this.runRoot, resolve(this.runRoot, "input-model.json"));
    const outputPath = contained(this.runRoot, resolve(this.runRoot, "final.ldr"));
    await writeFile(modelPath, JSON.stringify(model, null, 2) + "\n", "utf8");
    return invoke(["compile", modelPath, outputPath], this.options);
  }
  async demoGenerate(request: string, maxAttempts = 3): Promise<CommandResult> {
    if (!Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 3) throw new Error("maxAttempts must be an integer from 1 to 3");
    return invoke(["demo-generate", request, "--run-dir", this.runRoot, "--max-attempts", String(maxAttempts)], this.options);
  }
}

const modelSchema = Type.Object({ model: Type.Record(Type.String(), Type.Unknown()) });
export function createBrickBuilderTools(adapter: BrickBuilderAdapter): ToolDefinition[] {
  const tool = (name: string, description: string, parameters: any, execute: (id: string, p: any) => Promise<any>) => defineTool({ name, label: name, description, parameters, execute });
  return [
    tool("brick_catalog", "Inspect the supported Brick Builder palette.", Type.Object({}), async () => ({ content: [{ type: "text", text: JSON.stringify(await adapter.catalog()) }], details: {} })),
    tool("brick_validate", "Validate one canonical Brick Builder model.", modelSchema, async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.validate(p.model)) }], details: {} })),
    tool("brick_analyze", "Analyze one valid canonical Brick Builder model.", modelSchema, async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.analyze(p.model)) }], details: {} })),
    tool("brick_compile", "Compile one canonical model to LDraw inside this run.", modelSchema, async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.compile(p.model)) }], details: {} })),
    tool("brick_demo_generate", "Run the deterministic offline demo generation workflow.", Type.Object({ request: Type.String(), max_attempts: Type.Optional(Type.Integer({ minimum: 1, maximum: 3 })) }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.demoGenerate(p.request, p.max_attempts ?? 3)) }], details: {} })),
  ];
}

export function createPiSessionOptions(adapter: BrickBuilderAdapter): CreateAgentSessionOptions {
  // Pi's documented noTools mode suppresses its built-in filesystem and shell
  // tools while retaining the explicitly supplied custom domain tools.
  return { customTools: createBrickBuilderTools(adapter), noTools: "builtin" } as CreateAgentSessionOptions;
}

export async function readRunArtifact(runRoot: string, name: string): Promise<string> {
  return readFile(contained(runRoot, resolve(runRoot, name)), "utf8");
}

export async function runBounded<T>(attempts: number, operation: (attempt: number, feedback: unknown[]) => Promise<{ value?: T; feedback?: unknown[] }>, signal?: AbortSignal): Promise<{ value: T; attempts: number }> {
  if (!Number.isInteger(attempts) || attempts < 1 || attempts > 3) throw new Error("attempts must be an integer from 1 to 3");
  let feedback: unknown[] = [];
  for (let attempt = 1; attempt <= attempts; attempt++) {
    if (signal?.aborted) throw new Error("operation cancelled");
    const result = await operation(attempt, feedback);
    if (result.value !== undefined) return { value: result.value, attempts: attempt };
    feedback = result.feedback ?? feedback;
  }
  throw new Error(`bounded operation exhausted after ${attempts} attempts`);
}

export { operations };
