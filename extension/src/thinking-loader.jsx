import React from "react";
import { createRoot } from "react-dom/client";
import { InlineLoader, TextLoader } from "generative-loaders";
import "generative-loaders/styles.css";

let root = null;
const textRoots = new WeakMap();

export function mount(node) {
  root = createRoot(node);
  root.render(
    <InlineLoader
      variant="gravity"
      size={24}
      color="var(--accent)"
      label="thinking..."
    />
  );
}

export function unmount() {
  if (root) {
    root.unmount();
    root = null;
  }
}

export function mountText(node, text) {
  if (!node) return;
  const previous = textRoots.get(node);
  if (previous) previous.unmount();
  const next = createRoot(node);
  textRoots.set(node, next);
  next.render(
    <TextLoader
      text={String(text || "")}
      variant="terminal"
      color="var(--ink1)"
      aria-label="Desk answer"
    />
  );
}

export function unmountText(node) {
  const current = textRoots.get(node);
  if (current) {
    current.unmount();
    textRoots.delete(node);
  }
}
