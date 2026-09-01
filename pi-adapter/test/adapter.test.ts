import assert from "node:assert/strict";
import { mkdtemp, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";
import { BrickBuilderAdapter, createBrickBuilderTools, createPiSessionOptions, readRunArtifact, runBounded } from "../src/index.js";

const repo = resolve(import.meta.dirname, "../../..");
const python = join(repo, ".venv", "Scripts", "python.exe");
const model = JSON.parse(await readFile(join(repo, "examples/reference_models/rotated-one-stud.json"), "utf8"));

async function adapter() {
  const root = await mkdtemp(join(tmpdir(), "brick-builder-pi-"));
  return { root, api: new BrickBuilderAdapter({ runRoot: root, repositoryRoot: repo, python }) };
}

test("domain tools expose only the five Brick Builder operations", () => {
  const { api } = { api: new BrickBuilderAdapter({ runRoot: "C:/runs/test" }) };
  assert.deepEqual(createBrickBuilderTools(api).map((tool) => tool.name), ["brick_catalog", "brick_validate", "brick_analyze", "brick_compile", "brick_demo_generate"]);
  assert.equal((createPiSessionOptions(api) as any).noTools, "builtin");
});

test("catalog, validation, analysis and deterministic compilation stay offline", async () => {
  const { root, api } = await adapter();
  assert.equal((await api.catalog()).valid ?? true, true);
  assert.equal((await api.validate(model)).valid, true);
  assert.equal((await api.analyze(model)).valid, true);
  const one = await api.compile(model), bytes = await readFile(join(root, "final.ldr"));
  const two = await api.compile(model), bytes2 = await readFile(join(root, "final.ldr"));
  assert.equal(one.sha256, two.sha256);
  assert.deepEqual(bytes, bytes2);
  await stat(join(root, "input-model.json"));
});

test("malformed domain data is rejected and writes cannot escape run root", async () => {
  const { api } = await adapter();
  assert.equal((await api.validate({})).valid, false);
  await assert.rejects(() => api.demoGenerate("wall", 0), /maxAttempts/);
  await assert.rejects(() => readRunArtifact(api.runRoot, "../outside.txt"), /inside the caller-provided run root/);
});

test("bounded attempts, cancellation, and provider failure have explicit semantics", async () => {
  await assert.rejects(() => runBounded(2, async () => ({ feedback: [{ code: "bad" }] })), /exhausted after 2/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(() => runBounded(2, async () => ({ value: 1 }), controller.signal), /cancelled/);
  await assert.rejects(() => runBounded(1, async () => { throw new Error("provider unavailable"); }), /provider unavailable/);
  const result = await runBounded(3, async (attempt, feedback) => attempt === 2 ? { value: "accepted" } : { feedback: [{ attempt, feedback }] });
  assert.deepEqual(result, { value: "accepted", attempts: 2 });
});
