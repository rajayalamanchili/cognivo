#!/usr/bin/env node
// Minimal chromium-cli-style REPL for driving the Cognivo web app
// (frontend/, proxied to backend/) in a headless container.
// `chromium-cli` is not installed in this environment, but Playwright
// already ships as a frontend devDependency (used by tests/e2e/) --
// this script is a thin REPL wrapper around it with the same shape:
// pipe newline-separated commands to stdin, each line one action.
//
// Lives under frontend/scripts/ (not the skill dir) specifically so
// Node's ESM resolution finds `playwright` in frontend/node_modules --
// it walks up from the importing file's own path, not cwd, so a
// sibling-of-frontend location can never resolve it.
//
// Usage (run from anywhere; always resolves relative to this file):
//   node frontend/scripts/dev-browser-driver.mjs <<'EOF'
//   nav http://localhost:3000/demo
//   click text=/try as a demo learner/i
//   wait-for [data-testid="practice-start-form"]
//   screenshot 01-practice-start
//   console
//   EOF
//
// Commands:
//   nav <url>                    goto(url)
//   click <selector>              page.click(selector) -- Playwright
//                                  selector syntax, e.g. text=foo,
//                                  role=button[name="Submit"]
//   fill <selector> <text...>     page.fill(selector, text)
//   check <selector>              page.check(selector) (radio/checkbox)
//   wait-for <selector>           page.waitForSelector(selector)
//   wait-ms <n>                   page.waitForTimeout(n)
//   screenshot <name>             full-page PNG -> shots/<name>.png
//   eval <js>                     page.evaluate(js), result printed
//   console                       print collected console errors so far

import { chromium } from "playwright";
import { createInterface } from "node:readline";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const shotDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "shots");
mkdirSync(shotDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror[${page.url()}]: ${e.message}`));
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(`console[${page.url()}]: ${msg.text()}`);
});

function splitFirst(s, n) {
  const parts = s.split(" ");
  const head = parts.slice(0, n);
  const rest = parts.slice(n).join(" ");
  return [...head, rest];
}

const rl = createInterface({ input: process.stdin });
for await (const raw of rl) {
  const line = raw.trim();
  if (!line || line.startsWith("#")) continue;
  const [cmd, ...rest] = line.split(" ");
  try {
    if (cmd === "nav") {
      await page.goto(rest.join(" "), { waitUntil: "load" });
      console.log(`OK nav ${page.url()}`);
    } else if (cmd === "click") {
      await page.locator(rest.join(" ")).first().click();
      console.log(`OK click`);
    } else if (cmd === "fill") {
      const [selector, text] = splitFirst(rest.join(" "), 1);
      await page.fill(selector, text);
      console.log(`OK fill`);
    } else if (cmd === "check") {
      await page.locator(rest.join(" ")).first().check();
      console.log(`OK check`);
    } else if (cmd === "wait-for") {
      await page.waitForSelector(rest.join(" "), { timeout: 30000 });
      console.log(`OK wait-for`);
    } else if (cmd === "wait-ms") {
      await page.waitForTimeout(Number(rest[0]));
      console.log(`OK wait-ms`);
    } else if (cmd === "screenshot") {
      const name = rest.join(" ") || `shot-${Date.now()}`;
      await page.screenshot({ path: path.join(shotDir, `${name}.png`), fullPage: true });
      console.log(`OK screenshot ${path.join(shotDir, `${name}.png`)}`);
    } else if (cmd === "eval") {
      // eslint-disable-next-line no-eval
      const result = await page.evaluate(new Function(`return (${rest.join(" ")})`)());
      console.log(`OK eval ${JSON.stringify(result)}`);
    } else if (cmd === "console") {
      console.log(`CONSOLE_ERRORS ${JSON.stringify(errors)}`);
    } else if (cmd === "quit") {
      break;
    } else {
      console.log(`ERR unknown command: ${cmd}`);
    }
  } catch (err) {
    console.log(`ERR ${cmd}: ${err.message}`);
  }
}

await browser.close();
