import React from "react";
import { createRoot } from "react-dom/client";
import { InlineLoader } from "generative-loaders";
import "generative-loaders/styles.css";

let root = null;

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
