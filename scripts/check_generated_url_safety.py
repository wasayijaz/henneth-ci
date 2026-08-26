#!/usr/bin/env python3
"""Regression checks for generated URLs that become dashboard links."""

from pathlib import Path

from newslog_append import validated_http_url

ROOT = Path(__file__).resolve().parent.parent


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_newslog_ingestion():
    valid = "https://example.com/report.pdf?x=1#page=2"
    require(validated_http_url(valid) == valid, "valid https URL was not preserved")
    require(validated_http_url(" http://example.com/news ") == "http://example.com/news", "valid http URL was not trimmed")
    for bad in (
        "javascript:alert(1)",
        "data:text/html,<svg/onload=alert(1)>",
        "ftp://example.com/report.pdf",
        "https://",
        "http:example.com",
        "//example.com/path",
        "not a url",
        "",
    ):
        try:
            validated_http_url(bad)
        except ValueError:
            continue
        raise AssertionError(f"unsafe URL accepted: {bad!r}")


def check_dashboard_sinks():
    app = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    board = (ROOT / "dashboard" / "board.js").read_text(encoding="utf-8")
    require("function safeExternalHref" in app, "dashboard/app.js missing safeExternalHref")
    require("function externalLink" in app, "dashboard/app.js missing externalLink")
    for needle in (
        'href="${esc(cp.source_url)}"',
        'href="${esc(c.source_url)}"',
        'href="${esc(n.url)}"',
        'href="${esc(r.pdf_url)}"',
        'href="${esc(d.url)}"',
    ):
        require(needle not in app, f"dashboard/app.js still has raw generated href sink: {needle}")
    require('href="\' + esc(n.url) + \'"' not in board, "dashboard/board.js still has raw generated news href sink")
    require("noopener noreferrer" in app, "dashboard/app.js external links must include noopener noreferrer")


def main():
    try:
        check_newslog_ingestion()
        check_dashboard_sinks()
    except AssertionError as exc:
        print(f"x {exc}")
        raise SystemExit(1)
    print("OK generated URL safety")


if __name__ == "__main__":
    main()
