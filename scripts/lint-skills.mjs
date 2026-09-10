#!/usr/bin/env node
// Lint the skills directory. Run it before pushing; CI runs it on every push.
//
// In a skills repo the metadata is the product: the folder name decides how the
// skill is invoked, the description decides whether a model reaches for it at
// all, and that description is re-read on every single turn. So the checks here
// are about names and descriptions, not code.
//
// Exits non-zero on an error, zero on warnings alone.

import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const SKILLS = join(ROOT, "skills");

// Descriptions are always-on context, paid every turn whether or not the skill
// fires. Past roughly 60 words they are usually restating the body.
const DESC_WARN_WORDS = 60;
const DESC_ERROR_WORDS = 120;

const errors = [];
const warnings = [];

function frontmatter(text) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text);
  if (!m) return null;
  const fm = {};
  // Deliberately small: enough for `key: value` and folded/literal blocks,
  // which is all a SKILL.md header uses. Not a YAML parser.
  const lines = m[1].split(/\r?\n/);
  let key = null;
  let buf = [];
  const flush = () => {
    if (key) fm[key] = buf.join(" ").trim();
    key = null;
    buf = [];
  };
  for (const line of lines) {
    const kv = /^([A-Za-z_][A-Za-z0-9_-]*):\s?(.*)$/.exec(line);
    if (kv) {
      flush();
      key = kv[1];
      const v = kv[2].trim();
      buf = v === "|" || v === ">" || v === "|-" || v === ">-" ? [] : [v];
    } else if (key) {
      buf.push(line.trim());
    }
  }
  flush();
  return fm;
}

const names = new Map();

if (!existsSync(SKILLS)) {
  console.error("No skills/ directory at the repo root.");
  process.exit(1);
}

const dirs = readdirSync(SKILLS).filter((d) => statSync(join(SKILLS, d)).isDirectory());

for (const dir of dirs.sort()) {
  const file = join(SKILLS, dir, "SKILL.md");
  if (!existsSync(file)) {
    errors.push(`${dir}: no SKILL.md`);
    continue;
  }

  const text = readFileSync(file, "utf8");
  const fm = frontmatter(text);
  if (!fm) {
    errors.push(`${dir}: SKILL.md has no YAML frontmatter`);
    continue;
  }

  // The folder name is what the agent invokes. A frontmatter name that
  // disagrees is a silent routing bug: this repo shipped two of them.
  if (!fm.name) {
    errors.push(`${dir}: frontmatter has no 'name'`);
  } else if (fm.name !== dir) {
    errors.push(`${dir}: frontmatter name is '${fm.name}', should match the folder`);
  }

  if (fm.name) {
    if (names.has(fm.name)) {
      errors.push(`${dir}: duplicate skill name '${fm.name}', also in ${names.get(fm.name)}`);
    }
    names.set(fm.name, dir);
  }

  if (!fm.description) {
    errors.push(`${dir}: frontmatter has no 'description'; the model cannot know when to use it`);
  } else {
    const words = fm.description.split(/\s+/).filter(Boolean).length;
    if (words > DESC_ERROR_WORDS) {
      errors.push(`${dir}: description is ${words} words (limit ${DESC_ERROR_WORDS})`);
    } else if (words > DESC_WARN_WORDS) {
      warnings.push(`${dir}: description is ${words} words, over the ${DESC_WARN_WORDS}-word guide`);
    }
  }
}

for (const w of warnings) console.log(`warn   ${w}`);
for (const e of errors) console.error(`ERROR  ${e}`);

const total = dirs.length;
console.log(
  `\n${total} skills checked, ${errors.length} error(s), ${warnings.length} warning(s).`
);
process.exit(errors.length ? 1 : 0);
