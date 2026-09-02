import assert from "node:assert/strict";
import { mkdtemp, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { test } from "node:test";
import { BrickBuilderAdapter, createBrickBuilderTools, createPiSessionOptions, readRunArtifact, runBounded, runScriptedPiSession } from "../src/index.js";

const repo = resolve(import.meta.dirname, "../..");
const python = join(repo, ".venv", "Scripts", "python.exe");
const model = JSON.parse(await readFile(join(repo, "examples/reference_models/rotated-one-stud.json"), "utf8"));

async function adapter() {
  const root = await mkdtemp(join(tmpdir(), "brick-builder-pi-"));
  return { root, api: new BrickBuilderAdapter({ runRoot: root, repositoryRoot: repo, python }) };
}

test("domain tools expose only the explicit Brick Builder operations", () => {
  const { api } = { api: new BrickBuilderAdapter({ runRoot: "C:/runs/test" }) };
  assert.deepEqual(createBrickBuilderTools(api).map((tool) => tool.name), ["brick_catalog", "brick_validate", "brick_analyze", "brick_compile", "brick_demo_generate", "brick_demo_candidate_set", "brick_select_candidate", "brick_submit_brief", "brick_request_candidates", "brick_spatial_concepts", "brick_concept_redesign", "brick_legoize_concept", "brick_legoize_stepped_concept"]);
  assert.equal((createPiSessionOptions(api) as any).noTools, "builtin");
});

test("spatial concept submission preserves the request and writes deterministic previews", async () => {
  const { root, api } = await adapter();
  const response = {
    kind: "concepts",
    concepts: [1, 2].map((index) => ({
      id: `concept-${index}`,
      label: `box idea ${index}`,
      geometry: [{ ref: `concept-${index}/box-1`, center: [0, 0, 0], size: [4, 2, 3], color: "#2878b5" }],
      render: { camera: "three-quarter", width: 430, height: 360, scale: 24, geometry_refs: [`concept-${index}/box-1`] },
    })),
  };
  const result = await api.spatialConcepts("  Make a friendly rover!  ", response);
  assert.equal(result.status, "success");
  assert.equal(result.request_text, "  Make a friendly rover!  ");
  assert.ok(await stat(join(root, "render-concept-1.svg")));
  assert.ok(await stat(join(root, "spatial-concept-session.json")));
});

test("accepted concept redesign stays contained and preserves locked geometry", async () => {
  const { root, api } = await adapter();
  const concept = { id: "lookout-a", label: "A", geometry: [
    { ref: "base", center: [0, 0, 0], size: [4, 1, 4], color: "#2878b5" },
    { ref: "tower", center: [0, 2, 0], size: [2, 3, 2], color: "#f5a623" },
  ], render: { camera: "three-quarter", geometry_refs: ["base", "tower"] } };
  assert.equal((await api.conceptRedesign("start", { concept, requestText: "make a tiny lookout" })).valid, true);
  await api.conceptRedesign("focus", { point: [0, 0, 0], radius: 0.75, blockId: "base" });
  await api.conceptRedesign("lock");
  const proposal = await api.conceptRedesign("propose", { instruction: "make the tower taller" });
  assert.equal(proposal.valid, true);
  assert.deepEqual(((proposal.local_redesign as { proposal: { changed_ids: string[] } }).proposal).changed_ids, ["tower"]);
  await api.conceptRedesign("accept");
  const undone = await api.conceptRedesign("undo");
  assert.equal(undone.valid, true);
  assert.ok(await stat(join(root, "concept-redesign.json")));
});

test("aligned accepted concept LEGOizes through the deterministic bridge", async () => {
  const { root, api } = await adapter();
  const concept = { id: "box-a", label: "A box", geometry: [
    { ref: "box", center: [0, 2, 0], size: [4, 4, 2], color: "#2878b5" },
  ], render: { camera: "three-quarter", geometry_refs: ["box"] } };
  const result = await api.legoizeConcept(concept);
  assert.equal(result.valid, true);
  assert.equal((result.assembly as { coverage_complete: boolean }).coverage_complete, true);
  assert.equal((result.assembly as { structural_valid: boolean }).structural_valid, true);
  assert.ok(await stat(join(root, "legoization-bridge.json")));
  assert.ok(await stat(join(root, "final.ldr")));
});

test("aligned stepped concept LEGOizes through the deterministic bridge", async () => {
  const { root, api } = await adapter();
  const concept = { id: "step-a", label: "A stepped box", geometry: [
    { ref: "upper", center: [0, 1.5, 0], size: [2, 1, 2], color: "#2878b5" },
    { ref: "base", center: [0, 0.5, 0], size: [4, 1, 2], color: "#2878b5" },
  ], render: { camera: "three-quarter", geometry_refs: ["upper", "base"] } };
  const result = await api.legoizeSteppedConcept(concept);
  assert.equal(result.valid, true);
  assert.equal((result.assembly as { coverage_complete: boolean }).coverage_complete, true);
  assert.equal((result.assembly as { structural_valid: boolean }).structural_valid, true);
  assert.ok(await stat(join(root, "stepped-legoization-bridge.json")));
  assert.ok(await stat(join(root, "final.ldr")));
});

test("offline candidate replay and explicit selection stay contained and produce a receipt", async () => {
  const { root, api } = await adapter();
  const replay = await api.demoCandidateSet();
  assert.equal(replay.valid, true);
  assert.equal(replay.run_dir, join(root, "candidate-set"));
  const selected = await api.selectCandidate("gatehouse");
  assert.equal(selected.valid, true);
  assert.equal((selected as any).selection.selected_candidate_id, "gatehouse");
  const receipt = JSON.parse(await readRunArtifact(root, "selections/gatehouse/selection.json"));
  assert.equal(receipt.selected_candidate_id, "gatehouse");
  await assert.rejects(() => api.selectCandidate("missing" as any), /unknown offline candidate id/);
  await assert.rejects(() => api.demoCandidateSet("other" as any), /unknown offline candidate fixture/);
});

test("brief submission validates the bounded building contract and candidate replay is traceable", async () => {
  const { root, api } = await adapter();
  const brief = JSON.parse(await readFile(join(repo, "examples/demo/tiny-red-tower.brief.json"), "utf8"));
  const accepted = await api.submitBrief(brief);
  assert.equal(accepted.valid, true);
  const result = await api.requestCandidates("small-building-tower");
  assert.equal(result.valid, true);
  assert.deepEqual((result.candidate_index as Array<{ id: string }>).map((entry) => entry.id), ["compact-box", "stepped-box", "gatehouse"]);
  assert.ok(await stat(join(root, "brief.json")));
  assert.ok(await stat(join(root, "candidate-set", "candidate-index.json")));
  assert.ok(await stat(join(root, "candidate-set", "candidates", "gatehouse", "render-evidence.json")));
  assert.ok((result.manifest as { files: Record<string, string> }).files["candidate-index.json"]);
});

test("malformed and unsupported briefs are actionable and do not create candidate success", async () => {
  const { root, api } = await adapter();
  const malformed = await api.submitBrief({ format: "wrong", intent: "", constraints: { depth_studs: 3 } });
  assert.equal(malformed.valid, false);
  assert.match(JSON.stringify(malformed.issues), /BRIEF_FORMAT_UNSUPPORTED/);
  assert.equal((await api.requestCandidates("unknown-family")).valid, false);
  await assert.rejects(() => stat(join(root, "candidate-set")));
});

test("brief-to-candidate session repairs once, then exhausts without false success", async () => {
  const repaired = await adapter();
  const brief = JSON.parse(await readFile(join(repo, "examples/demo/tiny-red-tower.brief.json"), "utf8"));
  const repairedOutcome = await runScriptedPiSession(repaired.api, "submit a brief and request candidates", [
    { kind: "tool", name: "brick_submit_brief", arguments: { format: "wrong", intent: "", constraints: {} } },
    { kind: "tool", name: "brick_submit_brief", arguments: brief },
    { kind: "tool", name: "brick_request_candidates", arguments: { family: "small-building-tower" } },
    { kind: "text", text: "Candidate set ready." },
  ]);
  assert.equal(repairedOutcome.status, "completed");
  assert.deepEqual(repairedOutcome.toolCalls, ["brick_submit_brief", "brick_submit_brief", "brick_request_candidates"]);
  assert.ok(await stat(join(repaired.root, "candidate-set", "candidate-index.json")));
  const exhausted = await adapter();
  const exhaustedOutcome = await runScriptedPiSession(exhausted.api, "repair brief", [
    { kind: "tool", name: "brick_submit_brief", arguments: { format: "wrong", intent: "", constraints: {} } },
    { kind: "tool", name: "brick_submit_brief", arguments: { format: "wrong", intent: "", constraints: {} } },
    { kind: "text", text: "Unable to repair." },
  ]);
  assert.equal(exhaustedOutcome.status, "completed");
  await assert.rejects(() => stat(join(exhausted.root, "candidate-set")));
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

test("a scripted Pi session validates and compiles through only domain tools", async () => {
  const { root, api } = await adapter();
  const outcome = await runScriptedPiSession(api, "validate then compile this model", [
    { kind: "tool", name: "brick_validate", arguments: { model } },
    { kind: "tool", name: "brick_compile", arguments: { model } },
    { kind: "text", text: "Accepted." },
  ]);
  assert.equal(outcome.status, "completed");
  assert.deepEqual(outcome.toolCalls, ["brick_validate", "brick_compile"]);
  assert.equal(outcome.assistantText, "Accepted.");
  assert.equal(await readRunArtifact(root, "session-outcome.json"), JSON.stringify(outcome, null, 2) + "\n");
  await stat(join(root, "final.ldr"));
  assert.ok(outcome.artifactPath.startsWith(root));
});

test("scripted malformed calls and bounded repair/exhaustion are auditable", async () => {
  const malformed = await adapter();
  const malformedOutcome = await runScriptedPiSession(malformed.api, "validate", [
    { kind: "tool", name: "brick_validate", arguments: {} },
    { kind: "text", text: "Repair required." },
  ]);
  assert.equal(malformedOutcome.status, "completed");
  assert.deepEqual(malformedOutcome.toolCalls, ["brick_validate"]);
  const repaired = await adapter();
  const repairedOutcome = await runScriptedPiSession(repaired.api, "repair then compile", [
    { kind: "tool", name: "brick_validate", arguments: { model: {} } },
    { kind: "tool", name: "brick_validate", arguments: { model } },
    { kind: "text", text: "Repaired." },
  ]);
  assert.deepEqual(repairedOutcome.toolCalls, ["brick_validate", "brick_validate"]);
  await assert.rejects(() => runBounded(2, async () => ({ feedback: [{ code: "invalid" }] })), /exhausted after 2/);
});

test("a real scripted Pi session replays and selects an offline candidate", async () => {
  const { root, api } = await adapter();
  const outcome = await runScriptedPiSession(api, "replay the fixture and select gatehouse", [
    { kind: "tool", name: "brick_demo_candidate_set", arguments: {} },
    { kind: "tool", name: "brick_select_candidate", arguments: { candidate_id: "gatehouse" } },
    { kind: "text", text: "Gatehouse selected." },
  ]);
  assert.equal(outcome.status, "completed");
  assert.deepEqual(outcome.toolCalls, ["brick_demo_candidate_set", "brick_select_candidate"]);
  assert.equal(outcome.assistantText, "Gatehouse selected.");
  assert.equal(JSON.parse(await readRunArtifact(root, "selections/gatehouse/selection.json")).selected_candidate_id, "gatehouse");
});

test("scripted Pi candidate selection rejects unknown ids and escapes", async () => {
  const { root, api } = await adapter();
  const outcome = await runScriptedPiSession(api, "attempt unsafe selection", [
    { kind: "tool", name: "brick_select_candidate", arguments: { candidate_id: "../outside" } },
    { kind: "tool", name: "brick_demo_candidate_set", arguments: { fixture: "../../outside" } },
    { kind: "text", text: "Rejected." },
  ]);
  assert.equal(outcome.status, "completed");
  assert.deepEqual(outcome.toolCalls, ["brick_select_candidate", "brick_demo_candidate_set"]);
  assert.equal(outcome.assistantText, "Rejected.");
  await assert.rejects(() => readRunArtifact(root, "../outside/selection.json"), /inside the caller-provided run root/);
});

test("scripted cancellation and provider failure have deterministic outcomes", async () => {
  const cancelled = await adapter();
  const controller = new AbortController();
  const pending = runScriptedPiSession(cancelled.api, "wait", [{ kind: "delay", ms: 1000, response: { kind: "text", text: "late" } }], { signal: controller.signal });
  setTimeout(() => controller.abort(), 20);
  assert.equal((await pending).status, "cancelled");

  const failed = await adapter();
  const failure = await runScriptedPiSession(failed.api, "answer", [{ kind: "provider-error", message: "scripted provider unavailable" }]);
  assert.equal(failure.status, "provider-error");
  assert.equal(failure.toolCalls.length, 0);
});
