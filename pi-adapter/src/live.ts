import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { runConfiguredLiveConceptToCandidate } from "./live_run.js";

function usage(): string {
  return "Usage: pnpm live [--config <outside-repo-config.json>] --run-root <fresh-run-dir> [--max-attempts 1-3] [--python <python>] <ordinary request>";
}

export async function main(argv = process.argv.slice(2)): Promise<number> {
  let configPath: string | undefined;
  let runRoot: string | undefined;
  let python: string | undefined;
  let maxAttempts: number | undefined;
  const request: string[] = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--config") configPath = argv[++index];
    else if (arg === "--run-root") runRoot = argv[++index];
    else if (arg === "--python") python = argv[++index];
    else if (arg === "--max-attempts") maxAttempts = Number(argv[++index]);
    else if (arg === "--help" || arg === "-h") { console.log(usage()); return 0; }
    else request.push(arg);
  }
  if (!runRoot || request.length === 0) { console.error(usage()); return 2; }
  try {
    const outcome = await runConfiguredLiveConceptToCandidate({
      configPath: configPath ? resolve(configPath) : undefined,
      runRoot: resolve(runRoot),
      request: request.join(" "),
      maxAttempts,
      adapterOptions: python ? { python } : undefined,
    });
    console.log(JSON.stringify(outcome, null, 2));
    return outcome.status === "success" || outcome.status === "clarification" ? 0 : 1;
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 1;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  process.exitCode = await main();
}
