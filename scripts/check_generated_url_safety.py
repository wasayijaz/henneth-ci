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
    app = (ROOT / "Henneth Desk 2.CI.0" / "app.js").read_text(encoding="utf-8")
    require("const safeHref" in app, "CI app is missing safeHref")
    require("target=\"_blank\"" in app, "CI app source links must open in a separate tab")


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
