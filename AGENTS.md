# Local Explainer agent instructions

Read README.md first. Resolve machine-specific settings from environment variables or the ignored `.local-paths.json`; never commit personal paths or source material.

Keep output local. Durable lessons/models belong in the configured assets root, temporary files/logs/downloads/render frames in scratch, and final packages in builds. Defaults are under the ignored `data/` directory. Respect applicable parent workspace instructions.

Run pytest with an explicit `--basetemp` inside the configured scratch root. Preserve the outline approval gate: never approve a real lesson automatically or reuse test approval. Source repositories are read-only inputs. Do not upload source files or use cloud inference as an automatic fallback. Bind internal services to localhost and block external renderer requests.

The canonical chat skill lives in `skill/local-explainer`; installed copies are deployment artifacts. The canonical lesson schema lives in `explainer/schemas`. Do not vendor upstream checkouts, weights, runtime environments, user lessons, or generated packages into Git.
