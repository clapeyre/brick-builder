import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { isAbsolute, join, relative, resolve } from "node:path";
import {
  BrickBuilderAdapter,
  createBrickBuilderTools,
  createPiSessionOptions,
  type RunnerOptions,
} from "./index.js";
import {
  createAgentSession,
  ModelRuntime,
  SessionManager,
  SettingsManager,
  type CreateAgentSessionOptions,
} from "@earendil-works/pi-coding-agent";

export type LiveRunStatus = "clarification" | "success" | "failure" | "exhaustion" | "provider-failure";
export type LiveRunConfig = {
  provider: string;
  model: string;
  api: "openai-completions" | "openai-responses" | "anthropic-messages" | "google-generative-ai";
  baseUrl: string;
  apiKeyEnv?: string;
  authPath?: string;
  name?: string;
};

export type LiveRunContext = {
  request: string;
  runRoot: string;
  attempt: number;
  feedback: readonly unknown[];
  adapter: BrickBuilderAdapter;
  domainTools: ReturnType<typeof createBrickBuilderTools>;
  sessionOptions: ReturnType<typeof createPiSessionOptions>;
  provider?: string;
  model?: string;
};

export type LiveRunResult = {
  status: "clarification" | "success" | "failure" | "provider-failure";
  message?: string;
  trajectory?: unknown[];
  artifacts?: Record<string, unknown>;
  feedback?: unknown[];
};

export type LiveRunRunner = (context: LiveRunContext) => Promise<LiveRunResult>;
export type LiveSessionFactory = (context: LiveRunContext) => Promise<LiveRunRunner>;

export type LiveRunOptions = {
  runRoot: string;
  request: string;
  runner?: LiveRunRunner;
  sessionFactory?: LiveSessionFactory;
  adapterOptions?: Omit<RunnerOptions, "runRoot">;
  provider?: string;
  model?: string;
  maxAttempts?: number;
  signal?: AbortSignal;
};

export type ConfiguredLiveRunOptions = {
  runRoot: string;
  request: string;
  configPath: string;
  adapterOptions?: Omit<RunnerOptions, "runRoot">;
  maxAttempts?: number;
  signal?: AbortSignal;
  environment?: NodeJS.ProcessEnv;
};

export type LiveRunOutcome = {
  status: LiveRunStatus;
  request: string;
  attempts: number;
  message?: string;
  provider?: string;
  model?: string;
  artifactPath: string;
};

function contained(root: string, child: string): string {
  const base = resolve(root);
  const candidate = resolve(child);
  const rel = relative(base, candidate);
  if (rel === "" || rel === ".." || rel.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`) || isAbsolute(rel)) {
    throw new Error("path must remain inside the caller-provided run root");
  }
  return candidate;
}

function redact(value: unknown, key?: string): unknown {
  if (key && /(api[_-]?key|credential|password|secret|token)/i.test(key)) return "[REDACTED]";
  if (typeof value === "string") {
    return value
      .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer [REDACTED]")
      .replace(/\bsk-[A-Za-z0-9_-]{8,}\b/g, "[REDACTED]")
      .replace(/((?:api[_-]?key|password|secret|token)\s*[:=]\s*)[^\s,}\]]+/gi, "$1[REDACTED]");
  }
  if (Array.isArray(value)) return value.map((item) => redact(item));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([entryKey, entryValue]) => [entryKey, redact(entryValue, entryKey)]));
  }
  return value;
}

function outcomeMessage(result: LiveRunResult): string | undefined {
  return result.message?.trim() || undefined;
}

function safeLabel(value: string | undefined): string | undefined {
  return value && value.length <= 128 && /^[A-Za-z0-9._:/-]+$/.test(value) ? value : undefined;
}

function writeArtifactPath(runRoot: string, name: string): string {
  return contained(runRoot, resolve(runRoot, name));
}

/** Run one bounded provider session; the runner owns model interaction. */
export async function runLiveConceptToCandidate(options: LiveRunOptions): Promise<LiveRunOutcome> {
  const runRoot = resolve(options.runRoot);
  if (typeof options.request !== "string" || !options.request.trim()) throw new Error("request must be a non-empty string");
  const maxAttempts = options.maxAttempts ?? 3;
  if (!Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 3) throw new Error("maxAttempts must be an integer from 1 to 3");
  if ((options.runner ? 1 : 0) + (options.sessionFactory ? 1 : 0) !== 1) throw new Error("provide exactly one of runner or sessionFactory");

  await mkdir(runRoot, { recursive: true });
  if ((await readdir(runRoot)).length > 0) throw new Error("run root must be a fresh or empty caller-owned directory");
  const adapter = new BrickBuilderAdapter({ runRoot, ...options.adapterOptions });
  const domainTools = createBrickBuilderTools(adapter);
  const sessionOptions = createPiSessionOptions(adapter);
  const requestPath = writeArtifactPath(runRoot, "request.json");
  const trajectoryPath = writeArtifactPath(runRoot, "trajectory.json");
  const artifactPath = writeArtifactPath(runRoot, "live-run.json");
  await writeFile(requestPath, JSON.stringify({ request: options.request }, null, 2) + "\n", "utf8");

  const trajectory: unknown[] = [];
  let feedback: unknown[] = [];
  let attempts = 0;
  let final: LiveRunResult | undefined;
  while (attempts < maxAttempts) {
    attempts += 1;
    if (options.signal?.aborted) {
      final = { status: "failure", message: "operation cancelled" };
      break;
    }
    const context: LiveRunContext = { request: options.request, runRoot, attempt: attempts, feedback, adapter, domainTools, sessionOptions, provider: options.provider, model: options.model };
    try {
      const runner = options.runner ?? await options.sessionFactory!(context);
      const result = await runner(context);
      if (result.trajectory) trajectory.push({ attempt: attempts, events: redact(result.trajectory) });
      if (result.artifacts) trajectory.push({ attempt: attempts, artifacts: redact(result.artifacts) });
      if (result.status === "clarification" || result.status === "success" || result.status === "provider-failure") {
        final = result;
        break;
      }
      feedback = result.feedback ?? [];
      final = result;
    } catch (error) {
      final = { status: "provider-failure", message: error instanceof Error ? error.message : String(error) };
      break;
    }
  }
  const resolved = final ?? { status: "failure" as const, message: `bounded session exhausted after ${maxAttempts} attempts` };
  const status: LiveRunStatus = !final || (resolved.status === "failure" && attempts >= maxAttempts) ? "exhaustion" : resolved.status;
  const message = status === "exhaustion" ? `bounded session exhausted after ${maxAttempts} attempts` : outcomeMessage(resolved);

  await writeFile(trajectoryPath, JSON.stringify(trajectory, null, 2) + "\n", "utf8");
  const outcome: LiveRunOutcome = { status, request: options.request, attempts, message, provider: safeLabel(options.provider), model: safeLabel(options.model), artifactPath };
  await writeFile(artifactPath, JSON.stringify(redact(outcome), null, 2) + "\n", "utf8");
  return outcome;
}

const SUPPORTED_APIS = new Set<LiveRunConfig["api"]>(["openai-completions", "openai-responses", "anthropic-messages", "google-generative-ai"]);

export async function readLiveRunConfig(path: string): Promise<LiveRunConfig> {
  const value: unknown = JSON.parse(await readFile(resolve(path), "utf8"));
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("live config must be an object");
  const config = value as Record<string, unknown>;
  for (const key of ["provider", "model", "api", "baseUrl"]) {
    if (typeof config[key] !== "string" || !config[key].trim()) throw new Error(`live config ${key} must be a non-empty string`);
  }
  if (!SUPPORTED_APIS.has(config.api as LiveRunConfig["api"])) throw new Error(`unsupported live provider API: ${String(config.api)}`);
  if (config.apiKeyEnv !== undefined && (typeof config.apiKeyEnv !== "string" || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(config.apiKeyEnv))) throw new Error("live config apiKeyEnv must be an environment variable name");
  if (!/^https?:\/\//i.test(config.baseUrl as string)) throw new Error("live config baseUrl must be an http(s) URL");
  const result: LiveRunConfig = {
    provider: config.provider as string,
    model: config.model as string,
    api: config.api as LiveRunConfig["api"],
    baseUrl: config.baseUrl as string,
  };
  if (typeof config.apiKeyEnv === "string") result.apiKeyEnv = config.apiKeyEnv;
  if (typeof config.authPath === "string" && config.authPath.trim()) result.authPath = config.authPath;
  if (typeof config.name === "string") result.name = config.name;
  return result;
}

const LIVE_SYSTEM_PROMPT = `You are the bounded Brick Builder concept proposer. Use only the explicitly supplied Brick Builder domain tool.
Given the user's ordinary-language request, do exactly one of these:
1. Ask one concise, actionable clarification question of at most 240 characters, and do not call a tool; or
2. Call brick_concept_candidate_set with the original request and exactly two or three visibly distinct generic axis-aligned box concepts. If deterministic feedback rejects the proposal, repair it in the same session, at most twice. Do not select a candidate, rank candidates, access files or the shell, or invent tools. After a tool result, summarize its deterministic status and diagnostics without claiming resemblance or physical buildability.`;

function textFromMessage(message: any): string {
  return message?.content?.filter((part: any) => part.type === "text").map((part: any) => part.text).join("") ?? "";
}

function toolResultJson(result: any): Record<string, unknown> | undefined {
  const text = result?.content?.find((part: any) => part.type === "text")?.text;
  if (typeof text !== "string") return undefined;
  try {
    const value = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

function selectionReadyIndex(candidateSet: Record<string, unknown>): Record<string, unknown> | undefined {
  const candidates = candidateSet.candidates;
  if (!Array.isArray(candidates) || ![2, 3].includes(candidates.length)) return undefined;
  if (!candidates.every((candidate) => candidate && typeof candidate === "object" && (candidate as any).status === "success" && typeof (candidate as any).id === "string")) return undefined;
  return {
    format: "brick-builder.selection-ready/v1",
    candidate_set_hash: candidateSet.candidate_set_hash,
    candidates: candidates.map((candidate: any) => ({
      id: candidate.id,
      family: candidate.family,
      model_id: candidate.model_id,
      render_paths: [`candidates/${candidate.id}/render-front.svg`, `candidates/${candidate.id}/render-three-quarter.svg`, `candidates/${candidate.id}/final.ldr`],
    })),
  };
}

async function runConfiguredPiSession(context: LiveRunContext, config: LiveRunConfig, environment: NodeJS.ProcessEnv): Promise<LiveRunResult> {
  if (config.apiKeyEnv && !environment[config.apiKeyEnv]) return { status: "provider-failure", message: `configured credential environment variable ${config.apiKeyEnv} is not set` };
  const authPath = config.authPath ? resolve(config.authPath) : join(homedir(), ".pi", "agent", "auth.json");
  const runtime = await ModelRuntime.create({
    authPath,
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });
  const providerConfig: Record<string, unknown> = {
    name: config.name ?? config.provider,
    baseUrl: config.baseUrl,
    api: config.api,
    models: [{ id: config.model, name: config.model, api: config.api, reasoning: false, input: ["text"], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 128000, maxTokens: 4096 }],
  };
  if (config.apiKeyEnv) providerConfig.apiKey = `$${config.apiKeyEnv}`;
  runtime.registerProvider(config.provider, providerConfig as any);
  const model = runtime.getModel(config.provider, config.model);
  if (!model) return { status: "provider-failure", message: "configured provider did not expose the requested model" };
  const sessionOptions: CreateAgentSessionOptions = {
    ...context.sessionOptions,
    cwd: context.runRoot,
    agentDir: context.runRoot,
    modelRuntime: runtime,
    model,
    sessionManager: SessionManager.inMemory(context.runRoot),
    settingsManager: SettingsManager.create(context.runRoot, context.runRoot),
  };
  const sessionResult = await createAgentSession(sessionOptions);
  const events: unknown[] = [];
  const assistantTexts: string[] = [];
  let candidateSet: Record<string, unknown> | undefined;
  let candidateToolCalls = 0;
  let totalToolCalls = 0;
  let unexpectedToolCalls = 0;
  let toolBudgetExceeded = false;
  let providerError = false;
  const unsubscribe = sessionResult.session.subscribe((event: any) => {
    if (event.type === "tool_execution_start") {
      events.push({ type: event.type, tool_name: event.toolName, args: redact(event.args) });
      totalToolCalls += 1;
      if (event.toolName === "brick_concept_candidate_set") candidateToolCalls += 1;
      else unexpectedToolCalls += 1;
      if (totalToolCalls > 6 || candidateToolCalls > 3) {
        toolBudgetExceeded = true;
        void sessionResult.session.abort();
      }
    } else if (event.type === "tool_execution_end") {
      events.push({ type: event.type, tool_name: event.toolName, is_error: event.isError, result: redact(event.result) });
      if (event.toolName === "brick_concept_candidate_set" && !event.isError) candidateSet = toolResultJson(event.result);
    } else if (event.type === "message_end" && event.message?.role === "assistant") {
      if (event.message.stopReason === "error") providerError = true;
      const text = textFromMessage(event.message);
      if (text) assistantTexts.push(text);
      events.push({ type: event.type, role: "assistant", stop_reason: event.message.stopReason, text: redact(text) });
    }
  });
  try {
    const feedback = context.feedback.length ? `\nDeterministic feedback from the previous bounded attempt:\n${JSON.stringify(redact(context.feedback))}` : "";
    await sessionResult.session.prompt(`${LIVE_SYSTEM_PROMPT}${feedback}\n\nUser request:\n${context.request}`);
    await sessionResult.session.waitForIdle();
  } catch (error) {
    events.push({ type: "session_error", message: redact(error instanceof Error ? error.message : String(error)) });
    await sessionResult.session.abort();
    return { status: "provider-failure", message: error instanceof Error ? error.message : String(error), trajectory: events };
  } finally {
    unsubscribe();
    await sessionResult.session.abort();
  }
  if (providerError) return { status: "provider-failure", message: "provider returned a terminal error", trajectory: events };
  if (!toolBudgetExceeded && unexpectedToolCalls === 0 && candidateToolCalls > 0 && candidateSet) {
    const index = selectionReadyIndex(candidateSet);
    if (index) {
      await writeFile(writeArtifactPath(context.runRoot, "selection-ready.json"), JSON.stringify(index, null, 2) + "\n", "utf8");
      return { status: "success", trajectory: events, artifacts: { candidate_set: "candidate-set.json", selection_ready: "selection-ready.json", candidate_count: (index.candidates as unknown[]).length } };
    }
    return { status: "failure", message: "candidate composition was rejected or did not yield two or three valid candidates", feedback: [toolResultJson(candidateSet) ?? { code: "CANDIDATE_SET_INVALID" }], trajectory: events };
  }
  if (toolBudgetExceeded) return { status: "failure", message: "bounded live tool budget exceeded", feedback: [{ code: "LIVE_TOOL_BUDGET_EXCEEDED" }], trajectory: events };
  if (unexpectedToolCalls > 0) return { status: "failure", message: "model used an unexpected Brick Builder tool", feedback: [{ code: "LIVE_TOOL_NOT_ALLOWED" }], trajectory: events };
  const clarification = assistantTexts.at(-1)?.trim() ?? "";
  if (candidateToolCalls === 0 && clarification.length > 0 && clarification.length <= 240 && clarification.includes("?")) {
    return { status: "clarification", message: clarification, trajectory: events };
  }
  return { status: "failure", message: "model did not submit a valid candidate set or one actionable clarification", feedback: [{ code: "LIVE_CONTRACT_NOT_SATISFIED" }], trajectory: events };
}

/** Run one real, adult-configured provider using credentials supplied only by environment. */
export async function runConfiguredLiveConceptToCandidate(options: ConfiguredLiveRunOptions): Promise<LiveRunOutcome> {
  const config = await readLiveRunConfig(options.configPath);
  const environment = options.environment ?? process.env;
  return runLiveConceptToCandidate({
    runRoot: options.runRoot,
    request: options.request,
    adapterOptions: options.adapterOptions,
    provider: config.provider,
    model: config.model,
    maxAttempts: options.maxAttempts,
    signal: options.signal,
    sessionFactory: async () => async (context) => runConfiguredPiSession(context, config, environment),
  });
}
