/* Offline checks for the Today external-article adapter; no network or browser required. */
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("dashboard/today.js", "utf8");
const context = { window: {}, console, Date, URL, String, Number, Object, Array, Set };
vm.runInNewContext(source, context);
const article = context.window.HennethTodayArticle;
assert(article, "Today article adapter is exposed");

const rows = [
  { headline: "Undated should not win", ts: "not-a-date", summary: "bad timestamp" },
  { headline: "Older valid story", ts: "2026-09-03", url: "https://example.test/old" },
  { headline: "Newest valid story", ts: "2026-09-04", source: "Wire", summary: "Provided excerpt only.", url: "https://example.test/new" },
  { summary: "Headline missing" },
];
assert.equal(article.latest(rows).headline, "Newest valid story", "latest valid dated headline wins over malformed timestamp");
const sameDay = [{ headline: "Earlier same-day story", ts: "2026-09-04" }, { headline: "Later appended story", ts: "2026-09-04" }];
const sameDayBefore = JSON.stringify(sameDay);
assert.equal(article.latest(sameDay).headline, "Later appended story", "later append wins when newslog timestamps share a date");
assert.equal(JSON.stringify(sameDay), sameDayBefore, "latest selection does not mutate append-only input order");
assert.equal(article.href("https://example.test/a"), "https://example.test/a");
assert.equal(article.href("HTTP://example.test/a"), "HTTP://example.test/a");
assert.equal(article.href("https://"), "", "absolute-looking URL without a host is rejected");
assert.equal(article.href("javascript:alert(1)"), "", "javascript URL is rejected");
assert.equal(article.href("/blog/story"), "", "relative URL is not treated as an external article link");
assert.equal(article.href("data:text/html,hello"), "", "data URL is rejected");

const html = article.card(rows);
assert.match(html, /Newest valid story/);
assert.match(html, /ARTICLE/);
assert.match(html, /2026-09-04/);
assert.match(html, /Provided excerpt only\./);
assert.match(html, /href="https:\/\/example\.test\/new"/);
assert.match(html, /Read article/);
const escaped = article.card([{ headline: "<script>alert('x')</script>", source: "A&B", ts: "not-a-date", summary: "<b>no HTML</b>", url: "javascript:bad" }]);
assert.match(escaped, /&lt;script&gt;alert\(&#39;x&#39;\)&lt;\/script&gt;/, "headline is escaped");
assert.match(escaped, /A&amp;B/);
assert.match(escaped, /&lt;b&gt;no HTML&lt;\/b&gt;/);
assert.match(escaped, /date unknown/);
assert.doesNotMatch(escaped, /Read article/);
assert.equal(article.latest(null), null, "malformed feed has no article");
assert.equal(article.card([]), "", "empty feed renders no card");
assert.equal(article.card([{ headline: "   " }]), "", "blank headline renders no card");

console.log("today article checks passed (selection, malformed dates, safe links, escaping, empty feed)");
