#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("dashboard/today-info.js", "utf8");
const docHandlers = {};
class El {
  constructor(tag = "div", text = "") { this.tagName = tag.toUpperCase(); this.textContent = text; this.children = []; this.parentElement = null; this.attrs = {}; this.listeners = {}; this.hidden = false; this.style = {}; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  appendChild(c) { this.children.push(c); c.parentElement = this; return c; }
  insertBefore(c, ref) { const i = this.children.indexOf(ref); if (i < 0) this.children.push(c); else this.children.splice(i, 0, c); c.parentElement = this; return c; }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(x => x !== this); }
  removeChild(c) { this.children = this.children.filter(x => x !== c); }
  querySelector(sel) { if (sel.includes(".today-info-trigger")) return this.children.find(c => c.attrs.class === "today-info-trigger") || null; return null; }
  querySelectorAll() { return []; }
  matches(sel) { return sel === ".today-page" && this.attrs.class === "today-page"; }
  closest() { return this; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  focus() { documentStub.activeElement = this; }
  getBoundingClientRect() { return { left: 20, top: 20, bottom: 40, width: 100, height: 20 }; }
  contains(node) { return node === this || this.children.includes(node); }
}
const body = new El("body");
const heading = new El("p", "TODAY'S STANCE"); heading.setAttribute("class", "today-kicker");
const root = new El("main"); root.setAttribute("class", "today-page"); root.querySelectorAll = sel => {
  if (sel.includes(".today-kicker") && !sel.includes("canvas")) return [heading];
  return [];
};
const view = new El("div"); view.querySelector = sel => sel === ".today-page" ? root : null;
view.querySelectorAll = (...args) => root.querySelectorAll(...args);
const documentStub = {
  body, documentElement: { clientWidth: 1024, clientHeight: 768 }, activeElement: null,
  createElement: tag => new El(tag), getElementById: () => null,
  createTextNode: text => ({ textContent: text, parentElement: null }),
  addEventListener: (name, fn) => { docHandlers[name] = fn; },
};
const context = { window: {}, document: documentStub, console, setTimeout, clearTimeout, Math };
vm.runInNewContext(source, context);
assert(context.window.HennethTodayInfo, "Today info API exposed");
context.window.HennethTodayInfo.enhance(view);
assert.equal(heading.children.length, 1, "heading receives one info trigger");
const firstButton = heading.children[0];
assert.equal(firstButton.getAttribute("aria-label"), "About TODAY'S STANCE");
assert.equal(body.children.length, 1, "one popover is mounted");
const firstPanel = body.children[0];
firstButton.listeners.click();
assert.equal(firstPanel.hidden, false, "click opens popover");
assert.equal(firstButton.getAttribute("aria-expanded"), "true");
docHandlers.keydown({ key: "Escape" });
assert.equal(firstPanel.hidden, true, "Escape dismisses popover");
context.window.HennethTodayInfo.enhance(view);
assert.equal(heading.children.length, 1, "repeat enhance does not duplicate trigger");
assert.equal(body.children.length, 1, "repeat enhance removes stale popover");
assert(!body.children.includes(firstPanel), "stale popover is detached after rerender");
const freshButton = heading.children[0], freshPanel = body.children[0];
freshButton.listeners.pointerenter();
assert.equal(freshPanel.hidden, false, "hover opens the current popover");
freshButton.listeners.click({ stopPropagation() {} });
assert.equal(freshPanel.hidden, false, "first click pins a hover-opened popover");
freshButton.listeners.click({ stopPropagation() {} });
assert.equal(freshPanel.hidden, true, "second click closes a pinned popover");
freshButton.listeners.pointerenter();
docHandlers.pointerdown({ target: new El("div") });
assert.equal(freshPanel.hidden, true, "outside pointer dismisses popover");
console.log("today info checks passed (accessible labels, hover/click/Escape/outside dismissal, idempotent enhance)");
