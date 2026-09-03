import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Type } from "@sinclair/typebox";
import { createAgentSession, defineTool, ModelRuntime, SessionManager, SettingsManager, type ToolDefinition, type CreateAgentSessionOptions } from "@earendil-works/pi-coding-agent";
import { fauxAssistantMessage, fauxProvider, fauxToolCall, type FauxResponseStep } from "@earendil-works/pi-ai";

export type DomainOperation = "catalog" | "validate" | "analyze" | "compile" | "demo-generate" | "demo-candidate-set" | "select-candidate" | "submit-brief" | "request-candidates" | "spatial-concepts" | "concept-redesign" | "legoize-concept" | "legoize-stepped-concept" | "legoize-gatehouse-concept" | "concept-candidate-set" | "select-concept-candidate" | "selected-candidate-redesign";
export type RunnerOptions = { runRoot: string; python?: string; repositoryRoot?: string; signal?: AbortSignal };
export type CommandResult = { valid: boolean; [key: string]: unknown };

const operations = ["catalog", "validate", "analyze", "compile", "demo-generate", "demo-candidate-set", "select-candidate", "submit-brief", "request-candidates", "spatial-concepts", "concept-redesign", "legoize-concept", "legoize-stepped-concept", "legoize-gatehouse-concept", "concept-candidate-set", "select-concept-candidate", "selected-candidate-redesign"] as const;
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

async function invoke(args: string[], options: RunnerOptions, ensureRoot = true): Promise<CommandResult> {
  const root = resolve(options.runRoot);
  if (ensureRoot) await mkdir(root, { recursive: true });
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

  async submitBrief(brief: Record<string, unknown>): Promise<CommandResult> {
    const constraints = brief.constraints;
    const issues: Array<Record<string, string>> = [];
    if (brief.format !== "brick-builder.demo-brief/v1") issues.push({ code: "BRIEF_FORMAT_UNSUPPORTED", path: "format", message: "brief format must be brick-builder.demo-brief/v1", repair_hint: "Use the supported brief format exactly." });
    if (typeof brief.intent !== "string" || !brief.intent.trim()) issues.push({ code: "BRIEF_INTENT_REQUIRED", path: "intent", message: "brief intent must be a non-empty string", repair_hint: "Describe the small building in one short intent." });
    if (typeof constraints !== "object" || constraints === null || Array.isArray(constraints)) issues.push({ code: "BRIEF_CONSTRAINTS_REQUIRED", path: "constraints", message: "brief constraints must be an object", repair_hint: "Set constraints to an object with adult_supervised, depth_studs, and orthogonal." });
    else {
      const c = constraints as Record<string, unknown>;
      if (c.adult_supervised !== true) issues.push({ code: "ADULT_SUPERVISION_REQUIRED", path: "constraints.adult_supervised", message: "adult_supervised must be true", repair_hint: "This offline building flow requires adult_supervised: true." });
      if (c.orthogonal !== true) issues.push({ code: "ORTHOGONAL_REQUIRED", path: "constraints.orthogonal", message: "orthogonal must be true", repair_hint: "Use orthogonal: true for the supported building family." });
      if (c.depth_studs !== 2) issues.push({ code: "DEPTH_UNSUPPORTED", path: "constraints.depth_studs", message: "only depth_studs: 2 is supported", repair_hint: "Set depth_studs to 2." });
    }
    if (issues.length) return { valid: false, issues };
    const path = contained(this.runRoot, resolve(this.runRoot, "brief.json"));
    await writeFile(path, JSON.stringify(brief, null, 2) + "\n", "utf8");
    return { valid: true, brief_path: path, supported_family: "small-building-tower" };
  }

  async requestCandidates(family: string): Promise<CommandResult> {
    if (family !== "small-building-tower") return { valid: false, issues: [{ code: "FAMILY_UNSUPPORTED", path: "family", message: "only small-building-tower is supported", repair_hint: "Request family small-building-tower." }] };
    const brief = contained(this.runRoot, resolve(this.runRoot, "brief.json"));
    const repository = resolve(this.options.repositoryRoot ?? defaultRepo);
    const request = resolve(repository, "examples/demo/tiny-red-tower.request.txt");
    const candidates = resolve(repository, "examples/demo/candidate-set-towers-with-gatehouse.json");
    const candidateRoot = contained(this.runRoot, resolve(this.runRoot, "candidate-set"));
    return invoke(["demo-candidate-set", "--request-file", request, "--brief", brief, "--candidates", candidates, "--run-dir", candidateRoot], { ...this.options, runRoot: candidateRoot }, false);
  }

  async spatialConcepts(requestText: string, response: Record<string, unknown>): Promise<CommandResult> {
    if (typeof requestText !== "string" || !requestText.trim()) throw new Error("request must be a non-empty string");
    const requestPath = contained(this.runRoot, resolve(this.runRoot, "spatial-request.txt"));
    const responsePath = contained(this.runRoot, resolve(this.runRoot, "spatial-response.json"));
    await writeFile(requestPath, requestText, "utf8");
    await writeFile(responsePath, JSON.stringify(response, null, 2) + "\n", "utf8");
    return invoke(["spatial-concepts", "--request", requestPath, "--response", responsePath, "--run-dir", this.runRoot], this.options);
  }

  async conceptRedesign(operation: string, options: { concept?: Record<string, unknown>; requestText?: string; point?: number[]; radius?: number; blockId?: string; instruction?: string } = {}): Promise<CommandResult> {
    const args = ["concept-redesign", operation, "--run-dir", this.runRoot];
    if (operation === "start") {
      if (!options.concept) throw new Error("concept is required for redesign start");
      const conceptPath = contained(this.runRoot, resolve(this.runRoot, "accepted-concept.json"));
      await writeFile(conceptPath, JSON.stringify(options.concept, null, 2) + "\n", "utf8");
      args.push("--concept", conceptPath, "--request-text", options.requestText ?? "");
    }
    if (options.point) args.push("--point", JSON.stringify(options.point));
    if (options.radius !== undefined) args.push("--radius", String(options.radius));
    if (options.blockId) args.push("--block-id", options.blockId);
    if (options.instruction) args.push("--instruction", options.instruction);
    return invoke(args, this.options);
  }

  async legoizeConcept(concept: Record<string, unknown>, colour = 4): Promise<CommandResult> {
    const conceptPath = contained(this.runRoot, resolve(this.runRoot, "accepted-concept-for-legoization.json"));
    await writeFile(conceptPath, JSON.stringify(concept, null, 2) + "\n", "utf8");
    return invoke(["legoize-concept", "--concept", conceptPath, "--run-dir", this.runRoot, "--colour", String(colour)], this.options);
  }

  async legoizeSteppedConcept(concept: Record<string, unknown>, colour = 4): Promise<CommandResult> {
    const conceptPath = contained(this.runRoot, resolve(this.runRoot, "accepted-stepped-concept.json"));
    await writeFile(conceptPath, JSON.stringify(concept, null, 2) + "\n", "utf8");
    return invoke(["legoize-stepped-concept", "--concept", conceptPath, "--run-dir", this.runRoot, "--colour", String(colour)], this.options);
  }

  async legoizeGatehouseConcept(concept: Record<string, unknown>, colour = 4): Promise<CommandResult> {
    const conceptPath = contained(this.runRoot, resolve(this.runRoot, "accepted-gatehouse-concept.json"));
    await writeFile(conceptPath, JSON.stringify(concept, null, 2) + "\n", "utf8");
    return invoke(["legoize-gatehouse-concept", "--concept", conceptPath, "--run-dir", this.runRoot, "--colour", String(colour)], this.options);
  }

  async conceptCandidateSet(requestText: string, concepts: Array<Record<string, unknown>>): Promise<CommandResult> {
    if (typeof requestText !== "string" || !requestText.trim()) throw new Error("request must be a non-empty string");
    const requestPath = contained(this.runRoot, resolve(this.runRoot, "candidate-request.txt"));
    const conceptsPath = contained(this.runRoot, resolve(this.runRoot, "candidate-concepts.json"));
    await writeFile(requestPath, requestText, "utf8");
    await writeFile(conceptsPath, JSON.stringify(concepts, null, 2) + "\n", "utf8");
    return invoke(["concept-candidate-set", "--request", requestPath, "--concepts", conceptsPath, "--run-dir", this.runRoot], this.options);
  }

  async selectConceptCandidate(candidateId: string): Promise<CommandResult> {
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$/.test(candidateId)) throw new Error("candidate id must be a safe stable identifier");
    const candidateSet = contained(this.runRoot, resolve(this.runRoot, "candidate-set.json"));
    const selectionRoot = contained(this.runRoot, resolve(this.runRoot, "selection"));
    return invoke(["select-concept-candidate", "--candidate-set", candidateSet, "--candidate-id", candidateId, "--run-dir", selectionRoot], this.options);
  }

  async selectedCandidateRedesign(operation: string, options: { candidateId?: string; point?: number[]; radius?: number; blockId?: string; instruction?: string } = {}): Promise<CommandResult> {
    const args = ["selected-candidate-redesign", operation, "--run-dir", this.runRoot];
    if (operation === "start") {
      if (!options.candidateId) throw new Error("candidate_id is required for redesign start");
      const candidateSet = contained(this.runRoot, resolve(this.runRoot, "candidate-set.json"));
      args.push("--candidate-set", candidateSet, "--candidate-id", options.candidateId);
    }
    if (options.point) args.push("--point", JSON.stringify(options.point));
    if (options.radius !== undefined) args.push("--radius", String(options.radius));
    if (options.blockId) args.push("--block-id", options.blockId);
    if (options.instruction) args.push("--instruction", options.instruction);
    return invoke(args, this.options);
  }
}

const modelSchema = Type.Object({ model: Type.Record(Type.String(), Type.Unknown()) });
const conceptGeometrySchema = Type.Object({
  ref: Type.String({ minLength: 1, maxLength: 48 }),
  center: Type.Array(Type.Number(), { minItems: 3, maxItems: 3 }),
  size: Type.Array(Type.Number(), { minItems: 3, maxItems: 3 }),
  color: Type.String({ pattern: "^#[0-9a-fA-F]{6}$" }),
});
const conceptSchema = Type.Object({
  id: Type.String({ minLength: 1, maxLength: 48 }),
  label: Type.String({ minLength: 1 }),
  geometry: Type.Array(conceptGeometrySchema, { minItems: 1, maxItems: 12 }),
  render: Type.Object({
    camera: Type.Union(["front", "side", "top", "three-quarter"].map((value) => Type.Literal(value)) as any),
    geometry_refs: Type.Array(Type.String({ minLength: 1, maxLength: 48 }), { minItems: 1, maxItems: 12 }),
  }),
});
const conceptCandidateSetSchema = Type.Object({
  request: Type.String({ minLength: 1 }),
  concepts: Type.Array(conceptSchema, { minItems: 2, maxItems: 3 }),
});
const briefSchema = Type.Object({ format: Type.String(), intent: Type.String(), constraints: Type.Record(Type.String(), Type.Unknown()) });
const spatialResponseSchema = Type.Record(Type.String(), Type.Unknown());
const conceptRedesignSchema = Type.Object({
  operation: Type.Union(["start", "focus", "lock", "propose", "retry", "accept", "undo"].map((value) => Type.Literal(value)) as any),
  concept: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
  request: Type.Optional(Type.String()),
  point: Type.Optional(Type.Array(Type.Number(), { minItems: 3, maxItems: 3 })),
  radius: Type.Optional(Type.Number({ exclusiveMinimum: 0 })),
  block_id: Type.Optional(Type.String()),
  instruction: Type.Optional(Type.String()),
});
const selectedCandidateRedesignSchema = Type.Object({
  operation: Type.Union(["start", "focus", "lock", "propose", "retry", "accept", "undo"].map((value) => Type.Literal(value)) as any),
  candidate_id: Type.Optional(Type.String()),
  point: Type.Optional(Type.Array(Type.Number(), { minItems: 3, maxItems: 3 })),
  radius: Type.Optional(Type.Number({ exclusiveMinimum: 0 })),
  block_id: Type.Optional(Type.String()),
  instruction: Type.Optional(Type.String()),
});
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
    tool("brick_submit_brief", "Submit a small schema-validated creative brief; only the supported small-building vocabulary is accepted.", briefSchema, async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.submitBrief(p)) }], details: {} })),
    tool("brick_request_candidates", "Request the declared offline candidate set for an accepted brief. No paths or ranking are model-controlled.", Type.Object({ family: Type.String() }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.requestCandidates(p.family)) }], details: {} })),
    tool("brick_spatial_concepts", "Submit a bounded model response for a natural-language spatial concept request. The raw request and fixed previews are retained under the run root.", Type.Object({ request: Type.String(), response: spatialResponseSchema }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.spatialConcepts(p.request, p.response)) }], details: {} })),
    tool("brick_concept_redesign", "Focus, lock, propose, retry, accept, or undo a local redesign of one accepted generic-box concept. State stays inside this run root.", conceptRedesignSchema, async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.conceptRedesign(p.operation, { concept: p.concept, requestText: p.request, point: p.point, radius: p.radius, blockId: p.block_id, instruction: p.instruction })) }], details: {} })),
    tool("brick_legoize_concept", "LEGOize one accepted aligned generic-box concept through the deterministic one-box bridge. Coverage and structural validity remain separate evidence.", Type.Object({ concept: Type.Record(Type.String(), Type.Unknown()), colour: Type.Optional(Type.Integer({ minimum: 0 })) }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.legoizeConcept(p.concept, p.colour ?? 4)) }], details: {} })),
    tool("brick_legoize_stepped_concept", "LEGOize one accepted centered two-tier generic-box concept through the deterministic stepped bridge. Coverage and structural validity remain separate evidence.", Type.Object({ concept: Type.Record(Type.String(), Type.Unknown()), colour: Type.Optional(Type.Integer({ minimum: 0 })) }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.legoizeSteppedConcept(p.concept, p.colour ?? 4)) }], details: {} })),
    tool("brick_legoize_gatehouse_concept", "LEGOize one accepted bounded two-tower gatehouse concept through the deterministic gatehouse bridge. Coverage and structural validity remain separate evidence.", Type.Object({ concept: Type.Record(Type.String(), Type.Unknown()), colour: Type.Optional(Type.Integer({ minimum: 0 })) }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.legoizeGatehouseConcept(p.concept, p.colour ?? 4)) }], details: {} })),
    tool("brick_concept_candidate_set", "Evaluate exactly two or three generic axis-aligned box concepts. Use this exact JSON shape: each concept must be {id, label, geometry, render}; each geometry item must be {ref, center:[x,y,z], size:[width,height,depth], color:#rrggbb}; render must be {camera: front|side|top|three-quarter, geometry_refs:[refs in the same order as geometry]}. Preserve the user's ordinary-language request in request. This evaluates in input order and never ranks or selects.", conceptCandidateSetSchema, async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.conceptCandidateSet(p.request, p.concepts)) }], details: {} })),
    tool("brick_select_concept_candidate", "Explicitly select one successful candidate by stable ID and write a provenance receipt.", Type.Object({ candidate_id: Type.String() }), async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.selectConceptCandidate(p.candidate_id)) }], details: {} })),
    tool("brick_selected_candidate_redesign", "Focus, lock, propose, retry, accept, or undo a redesign rooted at an explicitly selected composed candidate; acceptance revalidates the original LEGOization family.", selectedCandidateRedesignSchema, async (_id, p) => ({ content: [{ type: "text", text: JSON.stringify(await adapter.selectedCandidateRedesign(p.operation, { candidateId: p.candidate_id, point: p.point, radius: p.radius, blockId: p.block_id, instruction: p.instruction })) }], details: {} })),
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
  // Keep Pi's runtime resource/auth locations inside the caller-owned run
  // root. No credentials are supplied; this prevents a scripted session from
  // touching a user-global ~/.pi directory.
  const runtime = await ModelRuntime.create({ authPath: resolve(adapter.runRoot, "pi-auth.json"), modelsPath: resolve(adapter.runRoot, "pi-models.json"), allowModelNetwork: false, refreshOnCreate: false });
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
    else if (providerTerminalError || responses.some((response) => response.kind === "provider-error")) status = "provider-error";
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    events.push(`error:${message}`);
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
