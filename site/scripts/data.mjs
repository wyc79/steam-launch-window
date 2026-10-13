// Builds the site's data files into public/data from a checkout of the data branch:
//   npm run data -- [--data-dir ../_data] [--gp-dir <folder>]
// Runs `python -m analysis.site_data` from the repository root (with the repo's
// .venv when there is one, else $PYTHON or python) and copies the data branch's
// site/model.json when present. Reads local files only.

import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { parseArgs } from "node:util";

const site = resolve(import.meta.dirname, "..");
const repo = resolve(site, "..");
const out = resolve(site, "public/data");
const { values } = parseArgs({ options: { "data-dir": { type: "string" }, "gp-dir": { type: "string" } } });
const dataDir = resolve(values["data-dir"] ?? resolve(repo, "_data"));

const venv = [".venv/Scripts/python.exe", ".venv/bin/python"].map((p) => resolve(repo, p)).find(existsSync);
const python = process.env.PYTHON ?? venv ?? "python";
const args = ["-m", "analysis.site_data", "--data-dir", dataDir, "--out", out];
if (values["gp-dir"]) args.push("--gp-dir", resolve(values["gp-dir"]));

const run = spawnSync(python, args, { cwd: repo, stdio: "inherit" });
if (run.status !== 0) process.exit(run.status ?? 1);

const model = resolve(dataDir, "site/model.json");
if (existsSync(model)) {
  copyFileSync(model, resolve(out, "model.json"));
  console.log(`copied ${model}`);
} else {
  console.log(`no ${model}: the page runs without the model`);
}
