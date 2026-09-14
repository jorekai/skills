# Generators

The app is produced by an official generator, and the convention is laid over it. `lay.py --flags` prints the command; the table below is the data the script holds, so a reader and the script never disagree. Everything the generator writes is the project's, except the files named in the last two columns: the root carries their job, so `lay.py` replaces the one and removes the other and records the replaced ones in the manifest.

| Generator | Directory | Command | Replaced by the root | Removed |
|---|---|---|---|---|
| `create-next-app` | `apps/web` | `pnpm dlx create-next-app@latest apps/web --ts --eslint --app --src-dir --import-alias "@/*" --use-pnpm --skip-install --no-tailwind --webpack --disable-git --no-agents-md --yes` | `apps/web/tsconfig.json`, `apps/web/next.config.ts`, `apps/web/src/app/page.tsx` | `apps/web/eslint.config.mjs`, `apps/web/.gitignore`, `apps/web/.git`, `apps/web/pnpm-workspace.yaml`, `apps/web/AGENTS.md`, `apps/web/CLAUDE.md` |

The flags are the ones that answer every prompt, so the command runs without a question; the source stands in `references/sources.md` of the router. The install is `pnpm install` after the generator, and again after `--wire` added the vendor modules of the chosen adapters; the browser the runner needs is installed once with `pnpm exec playwright install chromium`.

The vendor module ranges the wire step writes into the ports manifest are ranges, resolved by the install. The weekly workflow of this collection runs the generator, the wire and the gate for every axis pair, so a range that no longer resolves fails there and not on a person's machine.

A second generator costs one row in this table and one entry in the `GENERATORS` table of `scripts/lay.py`: its directory, its command, what the root replaces, what it removes. It costs no second template tree, because everything outside the app directory is the same for every generator.

What the app directory needs from the root is small: a `tsconfig.json` that extends the base and keeps the options the framework requires, a framework config that transpiles the four packages, a health route, the job route, and one browser test. Those five come from `templates/apps/web/` and are written when the app directory exists.
