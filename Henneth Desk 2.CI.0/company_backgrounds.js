(function exposeCompanyBackgroundRegistry(root) {
  "use strict";

  // Static, read-only seam for the Company Intelligence visual layer. Keep this
  // mapping deterministic: the first twenty assets are assigned to the current
  // pilot in symbol order; five remain explicitly reserved for future issuers.
  const ASSET_DIRECTORY = "product backgrounds";
  const pilot = Object.freeze({
    ATRL: "product-background-01.png",
    BOP: "product-background-02.png",
    CNERGY: "product-background-03.png",
    DGKC: "product-background-04.png",
    ENGROH: "product-background-05.png",
    FFC: "product-background-06.png",
    GAL: "product-background-07.png",
    HBL: "product-background-08.png",
    HUBC: "product-background-09.png",
    LUCK: "product-background-10.png",
    MARI: "product-background-11.png",
    MEBL: "product-background-12.png",
    MLCF: "product-background-13.png",
    NBP: "product-background-14.png",
    NRL: "product-background-15.png",
    OGDC: "product-background-16.png",
    PPL: "product-background-17.png",
    PRL: "product-background-18.png",
    PSO: "product-background-19.png",
    UBL: "product-background-20.png"
  });
  // Reserved (unassigned) slots: product-background-21.png through
  // product-background-25.png. Future companies must claim one explicitly.
  const reserved = Object.freeze([
    "product-background-21.png",
    "product-background-22.png",
    "product-background-23.png",
    "product-background-24.png",
    "product-background-25.png"
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
