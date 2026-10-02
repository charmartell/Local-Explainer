# Local Explainer

Turn local code, documents, designs, or a concept into a source-grounded narrated learning video. Review an outline, approve it, then generate an MP4, captions, illustrated transcript, and source report. Inference stays on your computer.

## Give this prompt to your agent

Copy this into your coding agent and fill in what you know. Leave unknown fields blank so the agent can inspect your machine or ask a focused question.

```text
Set up Local Explainer from https://github.com/charmartell/Local-Explainer.
Checkout folder: [choose a folder]
Operating system: [Windows version, or inspect]
GPU and available VRAM: [or inspect]
Storage folder / available space: [or inspect]
Install optional Codex skill: [yes/no]
Download local models: [yes/no]

Read README.md, AGENTS.md, and dependencies.json before changing anything.
Check prerequisites and hardware compatibility. Explain unsupported hardware
before attempting installation. Use the pinned dependencies and installer;
do not replace them with latest versions or silently use cloud inference.
Keep assets, scratch, builds, and ComfyUI configurable. Store machine-specific
paths in the ignored .local-paths.json and honor parent workspace instructions.
Preserve existing lessons, model assets, and modified upstream checkouts.
Run doctor, report missing components, and launch the localhost UI.

Then help me make this lesson:
Topic: [what I want to understand]
Sources: [absolute paths or public reference URLs]
Audience / assumed knowledge: [who this is for]
Learning goal: [what I should understand afterward]
Length: [1–20 minutes]
Mode: [offline / research]

Prepare the outline and show sources and gaps. Wait for my explicit approval
of that exact outline before production. Never approve on my behalf.
Keep source repositories read-only, renderer requests local, and inference local.
```

## Setup

The supported installer targets Windows, Python 3.12.10, and an NVIDIA driver compatible with the pinned CUDA 13 runtime. The local model stack was tested with 12 GB VRAM and 32 GB RAM; allow roughly 20 GB for model assets plus runtimes and generated media. Other platforms/hardware need runtime adaptation and are not covered by the installer.

Install Git and `uv`, clone this repository into your chosen folder, then run from the checkout:

```powershell
.\Install-Local-Explainer.ps1
.\Start-Local-Explainer.ps1
```

Open http://127.0.0.1:8090. Stop with `Stop-Local-Explainer.ps1`. First setup downloads pinned software/weights; local-source production can then run offline. `-SkipModels` skips weights and verification; `-SkipSkill` skips the optional chat skill. No API key or Codex installation is required for the application.

## Configurable storage

A fresh install keeps project-related dependencies and output together under ignored `data/` folders. You can choose separate drives without editing source code.

| Purpose | Default relative to checkout | Environment override |
| --- | --- | --- |
| Models, runtimes, lessons, references, source snapshots | `data/assets` | `LOCAL_EXPLAINER_ASSETS` |
| Downloads, logs, temporary media, tests | `data/scratch` | `LOCAL_EXPLAINER_SCRATCH` |
| Final video packages | `data/builds` | `LOCAL_EXPLAINER_BUILDS` |
| Pinned upstream ComfyUI checkout | `<assets>/Runtime/ComfyUI` | `LOCAL_EXPLAINER_COMFY_REPO` |

For persistent settings copy `.local-paths.example.json` to `.local-paths.json`, fill in absolute paths, and remove keys you want to leave at their defaults. Environment variables take precedence. Keep private paths and media out of commits. Moving existing storage requires updating stored artifact paths; changing these settings alone does not migrate lessons.

Model-service/voice settings live in `<assets>/config.json`; see [the usage guide](docs/usage.md#configuration). Internal endpoints must use localhost. Research mode sends the topic to a search provider and fetches public pages; source contents and inference prompts stay local.

## Agent and developer map

| Location | Responsibility |
| --- | --- |
| `AGENTS.md` | Agent constraints and verification |
| `explainer/` | Python application, pipeline, and served browser UI |
| `explainer/schemas/` | Canonical lesson schema |
| `scripts/` | Asset setup, UI build, production proof, integration demo |
| `skill/local-explainer/` | Canonical optional Codex skill and API helper |
| `dependencies.json` | Exact asset URLs, revisions, sizes, and hashes |
| `requirements-*.lock` | Pinned Python dependency inventories |
| `tests/` | Application checks |
| `docs/usage.md` | Browser workflow, storage management, CLI/API, limits |

The installer copies the skill into your Codex skills directory (under `CODEX_HOME` or your user profile). Set `LOCAL_EXPLAINER_REPO` to help the agent locate this checkout. Existing installed skills are preserved; compare/update them deliberately from the canonical copy.

From the checkout, load the shared paths before CLI or development work:

```powershell
$repoPath = (Get-Location).Path
. .\scripts\paths.ps1
$python = Join-Path $assetPath 'Runtime\app\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $python -m explainer.cli doctor
& $python -m pytest --basetemp (Join-Path $scratchPath 'pytest-output')
```

The checked-in browser JavaScript is ready to serve. To change the UI, run `npm ci` and `npm run build:ui`. The proof/integration scripts use local inference and create demo artifacts; they are separate from unit tests and never authorize a real lesson.

See [the usage guide](docs/usage.md) for lesson revisions, pause/resume, offline behavior, source handling, library offload, and validation limits. Upstream software and model distributions retain their own licenses; links and pinned assets are documented there and in `dependencies.json`.
