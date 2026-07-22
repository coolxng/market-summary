import { access, cp, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";

async function exists(path: string): Promise<boolean> {
  try { await access(path); return true; }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

export function sites(): Plugin {
  let root = process.cwd();
  return {
    name: "sites",
    apply: "build",
    configResolved(config) { root = config.root; },
    async closeBundle() {
      const output = resolve(root, "dist", ".openai");
      const hosting = resolve(root, ".openai", "hosting.json");
      await rm(output, { recursive: true, force: true });
      await mkdir(output, { recursive: true });
      if (await exists(hosting)) await cp(hosting, resolve(output, "hosting.json"));
    },
  };
}
