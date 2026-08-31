#!/usr/bin/env node
// Copies every subject's bundled images from the backend's own
// content-artifact directory into this frontend's public/ static
// output, so Next.js serves them with zero new frontend code beyond an
// <img> tag (research.md §1, spec 003 FR-005). Runs as an npm
// predev/prebuild hook -- see package.json.
//
// Node's built-in fs/path only -- no new dependency (research.md §1).

import { existsSync, mkdirSync, readdirSync, rmSync, cpSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const contentDir = resolve(scriptDir, "../../backend/content");
const publicImagesDir = resolve(scriptDir, "../public/content-images");

if (!existsSync(contentDir)) {
  console.error(
    `sync-content-images: backend/content not found at ${contentDir} -- ` +
      "this frontend build context can't see the sibling backend/ directory " +
      "(research.md §1's flagged Vercel monorepo risk). Failing the build " +
      "rather than shipping without images."
  );
  process.exit(1);
}

rmSync(publicImagesDir, { recursive: true, force: true });
mkdirSync(publicImagesDir, { recursive: true });

let subjectsWithImages = 0;
for (const entry of readdirSync(contentDir, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const subjectImagesDir = join(contentDir, entry.name, "images");
  if (!existsSync(subjectImagesDir)) continue;
  cpSync(subjectImagesDir, join(publicImagesDir, entry.name), { recursive: true });
  subjectsWithImages += 1;
}

console.log(
  `sync-content-images: synced images for ${subjectsWithImages} subject(s) into ${publicImagesDir}`
);
