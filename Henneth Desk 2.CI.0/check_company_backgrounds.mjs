import assert from "node:assert/strict";
import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const registryPath = join(here, "company_backgrounds.js");
const backgroundsPath = join(here, "product backgrounds");
const source = await readFile(registryPath, "utf8");
const context = vm.createContext({});
vm.runInContext(source, context, { filename: registryPath });
const registry = context.HENNETH_COMPANY_BACKGROUNDS;

const expectedPilot = {
    ATRL: "product-background-01.webp",
    BOP: "product-background-02.webp",
    CNERGY: "product-background-03.webp",
    DGKC: "product-background-04.webp",
    ENGROH: "product-background-05.webp",
    FFC: "product-background-06.webp",
    GAL: "product-background-07.webp",
    HBL: "product-background-08.webp",
    HUBC: "product-background-09.webp",
    LUCK: "product-background-10.webp",
    MARI: "product-background-11.webp",
    MEBL: "product-background-12.webp",
    MLCF: "product-background-13.webp",
    NBP: "product-background-14.webp",
    NRL: "product-background-15.webp",
    OGDC: "product-background-16.webp",
    PPL: "product-background-17.webp",
    PRL: "product-background-18.webp",
    PSO: "product-background-19.webp",
    UBL: "product-background-20.webp"
};
const expectedReserved = [21, 22, 23, 24, 25].map((n) => `product-background-${String(n).padStart(2, "0")}.webp`);

assert.ok(registry && registry.version === "ci-pilot-v1", "registry version is present");
assert.deepEqual({ ...registry.pilot }, expectedPilot, "pilot mapping is exact");
assert.deepEqual([...registry.pilotSymbols], Object.keys(expectedPilot), "pilot symbols are sorted and exact");
assert.deepEqual([...registry.reserved], expectedReserved, "reserved assets are explicit and exact");

const allAssets = (await readdir(backgroundsPath)).filter((name) => name.endsWith(".webp")).sort();
const expectedAssets = Object.values(expectedPilot).concat(expectedReserved).sort();
assert.deepEqual(allAssets, expectedAssets, "asset inventory contains exactly 25 expected WebP files");

const everyPath = Object.values(expectedPilot).concat(expectedReserved).map((name) => registry.pathFor ? registry.pathFor(name) : `${registry.assetDirectory}/${name}`);
for (const path of everyPath) {
  assert.match(path, /^product backgrounds\/product-background-\d{2}\.webp$/, `safe local path: ${path}`);
  assert.ok(!/^(?:[a-z][a-z0-9+.-]*:|[\\/])|\.\./i.test(path), `no network or traversal path: ${path}`);
  const info = await stat(join(here, path));
  assert.ok(info.size > 0 && info.size < 350_000, `optimized WebP loads at bounded size: ${path}`);
}
assert.equal(registry.forSymbol("mlcf"), "product backgrounds/product-background-13.webp", "symbol lookup normalizes case");
assert.equal(registry.forSymbol(" unknown "), null, "unknown symbol does not fall back to an asset");

const firstPass = registry.pilotSymbols.map((symbol) => registry.forSymbol(symbol));
const secondPass = registry.pilotSymbols.map((symbol) => registry.forSymbol(symbol));
assert.deepEqual(firstPass, secondPass, "assignments are deterministic");
assert.equal(new Set(firstPass).size, 20, "pilot assignments are distinct");
assert.ok(source.includes("Object.freeze"), "registry is exposed as read-only objects");
assert.ok(!/https?:\/\//i.test(source), "registry has no network URLs");

console.log(`company backgrounds contract: PASS (${allAssets.length} WebP assets, ${registry.pilotSymbols.length} pilot, ${registry.reserved.length} reserved)`);
