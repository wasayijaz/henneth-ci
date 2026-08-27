(function exposeCompanyBackgroundRegistry(root) {
  "use strict";

  // Static, read-only seam for the Company Intelligence visual layer. Keep this
  // mapping deterministic: the first twenty assets are assigned to the current
  // pilot in symbol order; five remain explicitly reserved for future issuers.
  const ASSET_DIRECTORY = "product backgrounds";
  const pilot = Object.freeze({
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
  });
  // Reserved (unassigned) slots: product-background-21.webp through
  // product-background-25.webp. Future companies must claim one explicitly.
  const reserved = Object.freeze([
    "product-background-21.webp",
    "product-background-22.webp",
    "product-background-23.webp",
    "product-background-24.webp",
    "product-background-25.webp"
  ]);
  const pilotSymbols = Object.freeze(Object.keys(pilot).sort());
  const pathFor = (file) => `${ASSET_DIRECTORY}/${file}`;
  const forSymbol = (symbol) => {
    const file = pilot[String(symbol || "").trim().toUpperCase()];
    return file ? pathFor(file) : null;
  };

  const registry = Object.freeze({
    version: "ci-pilot-v1",
    assetDirectory: ASSET_DIRECTORY,
    assetCount: 25,
    pilotSymbols,
    pilot,
    reserved,
    pathFor,
    forSymbol
  });

  Object.defineProperty(root, "HENNETH_COMPANY_BACKGROUNDS", {
    value: registry,
    writable: false,
    configurable: false,
    enumerable: true
  });
})(typeof globalThis === "object" ? globalThis : window);
