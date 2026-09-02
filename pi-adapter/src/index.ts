import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@sinclair/typebox";
import { createAgentSession, defineTool, ModelRuntime, SessionManager, SettingsManager, type ToolDefinition, type CreateAgentSessionOptions } from "@earendil-works/pi-coding-agent";
import { fauxAssistantMessage, fauxProvider, fauxToolCall, type FauxResponseStep } from "@earendil-works/pi-ai";

export type DomainOperation = "catalog" | "validate" | "analyze" | "compile" | "demo-generate" | "demo-candidate-set" | "select-candidate";
export type RunnerOptions = { runRoot: string; python?: string; repositoryRoot?: string; signal?: AbortSignal };
export type CommandResult = { valid: boolean; [key: string]: unknown };

const operations = ["catalog", "validate", "analyze", "compile", "demo-generate", "demo-candidate-set", "select-candidate"] as const;
const here = dirname(fileURLToPath(import.meta.url));
const defaultRepo = resolve(here, "../..");
export const OFFLINE_CANDIDATE_FIXTURE = "towers-with-gatehouse" as const;
export const OFFLINE_CANDIDATE_IDS = ["compact-box", "stepped-box", "gatehouse"] as const;
export type OfflineCandidateFixture = typeof OFFLINE_CANDIDATE_FIXTURE;
export type OfflineCandidateId = typeof OFFLINE_CANDIDATE_IDS[number];

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
  async demoCandidateSet(fixture: OfflineCandidateFixture = OFFLINE_CANDIDATE_FIXTURE): Promise<CommandResult> {
    if (fixture !== OFFLINE_CANDIDATE_FIXTURE) throw new Error(`unknown offline candidate fixture: ${fixture}`);
    const repositoryRoot = resolve(this.options.repositoryRoot ?? defaultRepo);
    const fixtureRoot = resolve(repositoryRoot, "examples", "demo");
    const request = resolve(fixtureRoot, "tiny-red-tower.request.txt");
    const brief = resolve(fixtureRoot, "tiny-red-tower.brief.json");
    const candidates = resolve(fixtureRoot, "candidate-set-towers-with-gatehouse.json");
    const run = contained(this.runRoot, join(this.runRoot, "candidate-set"));
    return invoke(["demo-candidate-set", "--request-file", request, "--brief", brief, "--candidates", candidates, "--run-dir", run], this.options);
  }
  async selectCandidate(candidateId: OfflineCandidateId): Promise<CommandResult> {
    if (!(OFFLINE_CANDIDATE_IDS as readonly string[]).includes(candidateId)) throw new Error(`unknown offline candidate id: ${candidateId}`);
    const source = contained(this.runRoot, join(this.runRoot, "candidate-set"));
    const destination = contained(this.runRoot, join(this.runRoot, "selections", candidateId));
    return invoke(["select-candidate", "--candidate-set-run", source, "--candidate-id", candidateId, "--destination", destination], this.options);
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
    tool("brick_demo_candidate_set", "Replay the checked-in offline three-candidate fixture.", Type.Object({ fixture: Type.Optional(Type.Literal(OFFLINE_CANDIDATE_FIXTURE)) }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.demoCandidateSet(p.fixture ?? OFFLINE_CANDIDATE_FIXTURE)) }], details: {} })),
    tool("brick_select_candidate", "Select one explicitly named candidate from the contained replay and write its receipt.", Type.Object({ candidate_id: Type.Union(OFFLINE_CANDIDATE_IDS.map((id) => Type.Literal(id)) as any) }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.selectCandidate(p.candidate_id)) }], details: {} })),
  ];
}

export function createPiSessionOptions(adapter: BrickBuilderAdapter): CreateAgentSessionOptions {
  // Pi's documented noTools mode suppresses its built-in filesystem and shell
  // tools while retaining the explicitly supplied custom domain tools.
  return { customTools: createBrickBuilderTools(adapter), noTools: "builtin" } as CreateAgentSessionOptions;
}

export type ScriptedPiResponse =
  | { kind: "text"; text: string }
  | { kind: "tool"; name: string; arguments: Record<string, unknown>; id?: string }
  | { kind: "provider-error"; message: string }
  | { kind: "delay"; ms: number; response: Exclude<ScriptedPiResponse, { kind: "delay" }> };

export type PiSessionOutcome = {
  status: "completed" | "cancelled" | "provider-error" | "session-error";
  assistantText: string;
  toolCalls: string[];
  events: string[];
  artifactPath: string;
};

function scriptedStep(response: ScriptedPiResponse): FauxResponseStep {
  if (response.kind === "text") return fauxAssistantMessage(response.text);
  if (response.kind === "tool") return fauxAssistantMessage(fauxToolCall(response.name, response.arguments, { id: response.id }));
  if (response.kind === "provider-error") return async () => { throw new Error(response.message); };
  return async (_context, options, _state, _model) => {
    await new Promise<void>((resolvePromise, reject) => {
      const timer = setTimeout(resolvePromise, response.ms);
      options?.signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new Error("operation cancelled")); }, { once: true });
    });
    return scriptedStep(response.response) instanceof Function
      ? (scriptedStep(response.response) as any)(_context, options, _state, _model)
      : scriptedStep(response.response);
  };
}

/** Run one real Pi AgentSession against deterministic in-memory model responses. */
export async function runScriptedPiSession(
  adapter: BrickBuilderAdapter,
  prompt: string,
  responses: ScriptedPiResponse[],
  options: { signal?: AbortSignal } = {},
): Promise<PiSessionOutcome> {
  const faux = fauxProvider({ provider: "brick-builder-scripted", models: [{ id: "offline-script", name: "Offline scripted model" }] });
  faux.setResponses(responses.map(scriptedStep));
  const runtime = await ModelRuntime.create({ allowModelNetwork: false, refreshOnCreate: false });
  runtime.registerNativeProvider(faux.provider);
  const sessionResult = await createAgentSession({
    ...createPiSessionOptions(adapter),
    cwd: adapter.runRoot,
    model: faux.getModel(),
    modelRuntime: runtime,
    sessionManager: SessionManager.inMemory(adapter.runRoot),
    settingsManager: SettingsManager.create(adapter.runRoot, adapter.runRoot),
  });
  const events: string[] = [], toolCalls: string[] = [], assistant: string[] = [];
  let providerTerminalError = false;
  const unsubscribe = sessionResult.session.subscribe((event: any) => {
    if (event.type === "tool_execution_start") { toolCalls.push(event.toolName); events.push(`tool:start:${event.toolName}`); }
    else if (event.type === "tool_execution_end") events.push(`tool:end:${event.toolName}`);
    else if (event.type === "message_end" && event.message?.role === "assistant") {
      // Pi surfaces provider failures as a terminal assistant message rather than
      // rejecting prompt()/waitForIdle(). Preserve that signal for the wrapper's
      // outcome classification while leaving normal and cancelled turns alone.
      if (event.message.stopReason === "error") providerTerminalError = true;
      const text = event.message.content?.filter((part: any) => part.type === "text").map((part: any) => part.text).join("") ?? "";
      if (text) assistant.push(text);
    } else events.push(event.type);
  });
  const abortSession = () => { void sessionResult.session.abort(); };
  options.signal?.addEventListener("abort", abortSession, { once: true });
  let status: PiSessionOutcome["status"] = "completed";
  try {
    if (options.signal?.aborted) throw new Error("operation cancelled");
    await sessionResult.session.prompt(prompt);
    await sessionResult.session.waitForIdle();
    if (options.signal?.aborted) status = "cancelled";
    else if (providerTerminalError) status = "provider-error";
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    status = /cancel/i.test(message) ? "cancelled" : /provider|unavailable/i.test(message) ? "provider-error" : "session-error";
  } finally { options.signal?.removeEventListener("abort", abortSession); unsubscribe(); await sessionResult.session.abort(); }
  const artifactPath = contained(adapter.runRoot, resolve(adapter.runRoot, "session-outcome.json"));
  const outcome: PiSessionOutcome = { status, assistantText: assistant.join("\n"), toolCalls, events, artifactPath };
  await writeFile(artifactPath, JSON.stringify(outcome, null, 2) + "\n", "utf8");
  return outcome;
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
