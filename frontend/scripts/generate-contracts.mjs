import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const backend = fileURLToPath(new URL("../../backend/", import.meta.url));
// Pydantic uses JSON Schema 2020-12. The compiler understands draft-07 tuples.
// Property titles are presentation metadata, not distinct named type definitions.
function normalize(node) {
  if (!node || typeof node !== "object") return;
  for (const property of Object.values(node.properties ?? {}))
    delete property.title;
  if (node.prefixItems) {
    node.items = node.prefixItems;
    node.additionalItems = false;
    delete node.prefixItems;
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(normalize);
    else normalize(value);
  }
}
for (const [module, exported] of [
  ["jobflow", "ContractExport"],
  ["broker", "BrokerContractExport"],
  ["improvement", "ImprovementContractExport"],
  ["run", "CatalogRunContractExport"],
  ["catalog_improvement", "CatalogImprovementContractExport"],
]) {
  const target = new URL(`../lib/${module}.generated.ts`, import.meta.url);
  const raw = execFileSync(
    "uv",
    [
      "run",
      "--locked",
      "--directory",
      backend,
      "python",
      "-c",
      `import json; from app.contracts.${module} import ${exported}; print(json.dumps(${exported}.model_json_schema(), sort_keys=True))`,
    ],
    { encoding: "utf8", windowsHide: true, maxBuffer: 4 * 1024 * 1024 },
  );
  const schema = JSON.parse(raw);
  normalize(schema);
  const output = await compile(schema, exported, {
    bannerComment: `/* Generated from backend/app/contracts/${module}.py. Do not edit. Run npm run generate. */`,
    additionalProperties: false,
    style: { singleQuote: false, semi: true, tabWidth: 2 },
  });
  if (process.argv.includes("--check")) {
    if ((await readFile(target, "utf8")) !== output)
      throw new Error(`Contract drift in ${module}: run npm run generate`);
  } else {
    await mkdir(new URL("../lib/", import.meta.url), { recursive: true });
    await writeFile(target, output, "utf8");
  }
}
