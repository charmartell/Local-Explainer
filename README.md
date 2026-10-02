# Local Explainer

A local application for turning a concept, repository, design, or process into a narrated learning video.

**Choose sources → review a brief outline → generate and watch.**

## Use it

Run `Start-Local-Explainer.ps1` from this directory, then open **http://127.0.0.1:8090**. The launcher reuses an existing server.

1. Open **Composer** and enter a topic. Drag in documents, code, design images, folders, or reference links; use **Choose repository** or **Choose files** for the native Windows picker. You can also enter absolute paths, one per line. Folder drops become local snapshots; the repository picker reads the original Git checkout. Unsupported files and secret/build folders are excluded.
2. Choose **Offline** to use local files and the cached reference library. A new concept without sources needs **Local models + web research**, or your own local reference files.
3. Choose a narrator, preview the voice, and move **Explanation depth** from shortform to longform (about 1–20 minutes). Longer lessons include more causal steps, worked examples, and supported failure paths. Set **Demo / test** for practice content. Review the outline, its sources, and any gaps. **Generate my video** approves that exact outline and starts production.
4. Watch the video. Download the MP4, captions, illustrated transcript, or source report. Chapter buttons jump within the video.

**Make an adjustment** can revise the whole lesson, with a fresh outline, or one selected scene within its approved chapter. Other scenes reuse saved audio, images, and video clips. **Pause generation** preserves completed work; **Resume** continues after cancellation, failure, or a restart.

## Library and storage

The sidebar groups a lesson's revisions together. Expand **earlier revisions** to inspect the history. Search by title/topic, filter **Drafts**, **Videos**, **Demos**, **In progress**, or **Offloaded**, and sort by update or creation time. Creation and update timestamps appear on lessons and library rows. Older implementation fixtures are classified as demos; **Mark as demo / lesson** can change the category.

Open **Library & storage** to see local lesson/media sizes and free space on the working drive. Check multiple lessons or **Select visible**. Selection includes all versions of each selected lesson. Active jobs must be paused before their storage can be managed.

- **Offload selected** opens a destination folder picker and a review dialog. The application copies source snapshots, working media, and final packages, verifies file hashes, records the destination, then removes its local copies. Choose a different drive to free space on the current drive. Videos can play from the archive while that drive is available. **Restore** verifies and copies a lesson back before editing or resuming it.
- **Delete selected** previews the selected titles, version count, and bytes. A confirmation checkbox is required before permanent deletion. This removes those lessons and media, including their offloaded copies. Original source repositories/files, model weights, and runtimes are preserved.

Drag-and-drop transfers stay on localhost and are limited to 10 MB per file, 100 MB per batch, and 400 files. Larger repositories should use the native picker. Dropped source copies are stored under `Assets/Inputs`; their size is shown separately from lesson/media storage. Composer text and settings persist in this browser.

No account, API key, cloud inference, or Explain Video Generator plugin is required. The independent application works without Codex. The optional Codex skill coordinates it from chat; Codex's own reasoning runs according to your Codex configuration.

## Installed on this computer

| Task | Local component |
| --- | --- |
| Lesson planning, script, evidence review | Qwen3 8B Q4_K_M through llama.cpp Vulkan |
| Read design images | Qwen3-VL 4B Q4_K_M and local vision projector |
| Editorial illustrations | FLUX.2 klein 4B through ComfyUI, with CPU offload |
| Narration | Kokoro 82M; Heart, Bella, Nicole, Adam, and Michael, with English resources installed locally |
| Exact diagrams and code | HTML/SVG, Pygments, Chromium/Playwright |
| Motion and final encoding | FFmpeg, H.264/AAC, 1920×1080 at 30 FPS |
| Application | FastAPI, SQLite/FTS5, TypeScript browser UI |

Models use the GPU sequentially so image generation and language generation do not compete for the RTX 5070's 12 GB of VRAM. Speech runs on the CPU. Diagram emphasis changes with sentence narration; scenes have gentle camera motion and fades. This version does not generate free-form AI video footage.

## Where files live

| Location | Contents |
| --- | --- |
| `C:\Dev\Local-Explainer` | This application's source repository |
| `C:\Dev\ComfyUI-Local-Explainer` | Pinned upstream ComfyUI checkout |
| `C:\Dev\_assets\Local-Explainer\Runtime` | Python environments, llama.cpp, Chromium |
| `C:\Dev\_assets\Local-Explainer\Models` | Model weights and local speech resources |
| `C:\Dev\_assets\Local-Explainer\Lessons` | Source snapshots, outlines, authored scenes, approval records |
| `C:\Dev\_assets\Local-Explainer\References` | Cached public reference text |
| `C:\Dev\_scratch\Local-Explainer` | Logs, downloads, narration WAVs, frames, intermediate clips, test fixtures |
| `C:\Dev\_builds\Local-Explainer` | Final video packages |

The three application roots can be changed with `LOCAL_EXPLAINER_ASSETS`, `LOCAL_EXPLAINER_SCRATCH`, and `LOCAL_EXPLAINER_BUILDS` before launching. Windows and an NVIDIA GPU are the tested target. Other hardware requires adapting the inference runtime.

## Offline and research behavior

Offline mode does not search or fetch source URLs. URLs work only when already cached. Narration rejects attempted network connections. ComfyUI starts with offline mode and its API nodes disabled. Model endpoints accept only localhost URLs; Chromium scene rendering blocks external requests.

Research mode sends the **topic** to a search provider and fetches public reference pages. Automatic discovery selects recognized primary documentation/research domains; unfamiliar topics can use explicit author documentation URLs. Source contents and inference prompts go only to the local models. Research is currently HTML/text extraction; supply PDFs as local files. Cached references can be reused offline.

Repositories are inspected without executing their code. Secret filenames, environment files, build trees, symlinks, and large files are excluded. The initial repository snapshot reads at most roughly 500,000 text characters, with up to 1,000 file hashes, rather than loading every file in a large monorepo. For detailed lessons, point at the relevant package or module as well as the repository root. Uncommitted tracked file contents are captured; Git commit metadata is context, not a claim that the working tree matches that commit.

Design images use local vision analysis. They provide evidence about visible layout; inferred intent is distinguished from implemented behavior. Text PDFs are supported; scanned PDFs need an OCR/text export. Binary design formats should be exported to PNG, SVG, PDF, or Markdown.

## Setup on another Windows machine

Prerequisites: Git, `uv`, an NVIDIA driver compatible with the pinned CUDA 13 runtime, and enough disk space for roughly 20 GB of model assets plus runtimes and intermediate media. This setup is tested on an i9-14900F, 32 GB RAM, RTX 5070 12 GB. First setup downloads software and weights; later production with local sources can operate offline.

```powershell
Set-Location C:\Dev\Local-Explainer
.\Install-Local-Explainer.ps1
.\Start-Local-Explainer.ps1
```

Setup uses Python 3.12.10, pinned package inventories, ComfyUI commit `170594057a22673349ddf0a3d88624b7fa5865bb`, and exact model revisions/checksums in `dependencies.json`. Interrupted model downloads resume. Existing assets are checksum checked. Setup preserves an existing modified ComfyUI checkout or skill and asks you to resolve the version difference instead of overwriting it.

`-SkipModels` skips model downloads and verification; `-SkipSkill` skips installing the chat skill. Models remain independently managed assets. No system Python packages are changed.

The installed skill is `C:\Users\Charles\.codex\skills\local-explainer`. Use `$local-explainer` in a new Codex chat after skill discovery refreshes. Its localhost API helper avoids competing inference processes.

## Configuration

Optional `C:\Dev\_assets\Local-Explainer\config.json`:

```json
{
  "llama_url": "http://127.0.0.1:8091",
  "comfy_url": "http://127.0.0.1:8092",
  "voice": "af_heart",
  "search_url": ""
}
```

`search_url` accepts a public SearXNG-compatible JSON search endpoint; otherwise discovery uses DDGS. Internal model services start on demand and stop after their job. An externally started llama.cpp service cannot automatically switch to vision analysis; stop it before an image-input job. Closing the browser does not stop the background application. Run `Stop-Local-Explainer.ps1` to shut down cleanly and save resumable state for active jobs.

## CLI and API

Prefer the browser or skill API helper while the server is running. A standalone CLI job is synchronous; do not run competing CLI production against the browser's job queue.

```powershell
$python = 'C:\Dev\_assets\Local-Explainer\Runtime\app\Scripts\python.exe'
& $python -m explainer.cli doctor
& $python -m explainer.cli status
& $python -m explainer.cli plan --request C:\Dev\_scratch\Local-Explainer\requests\lesson.json
# Only after the user reviews and approves the returned outline:
& $python -m explainer.cli approve LESSON_ID --outline-hash REVIEWED_HASH
& $python -m explainer.cli produce LESSON_ID
& $python -m explainer.cli revise LESSON_ID --scene-id SCENE_ID --instruction 'Explain with a simpler example'
```

Request example:

```json
{
  "topic": "How this repository processes a request",
  "inputs": ["C:\\Dev\\my-repository"],
  "goal": "Understand the components and one complete data path",
  "audience": "Curious builder; explain unfamiliar terms",
  "minutes": 6,
  "mode": "offline"
}
```

Local API documentation: **http://127.0.0.1:8090/docs**. The important operations are `/api/jobs`, `/approval`, `/production`, `/cancel`, `/resume`, and `/revisions` beneath a job. Production rejects an absent or stale outline approval. The server binds to 127.0.0.1 and rejects foreign hosts and origins.

## Verification and limits

Implemented checks: JSON schema, resolved evidence IDs, exact captured code excerpts, graph references, approval hash, scene layout bounds, local asset existence, and full final-video decode. Each chapter also receives a local model review of source support and one repair attempt. This review can miss semantic mistakes; inspect the source report for consequential claims. Caption chunks use measured sentence audio with estimated word timing, not forced alignment. Requested video length is approximate.

The production proof is a 92-second video combining local speech, a locally generated illustration, exact code, and a diagram. `scripts/integration_demo.py` additionally tests actual ingestion, outline creation, script generation, evidence review, and video production with a small owned queue-worker fixture. Its test approval is explicitly labeled and does not approve a user lesson.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'C:\Dev\_assets\Local-Explainer\Runtime\app\Scripts\python.exe'
& $python -m pytest --basetemp C:\Dev\_scratch\Local-Explainer\pytest-output
$env:PYTHONPATH = 'C:\Dev\Local-Explainer'
& $python scripts\proof.py
& $python scripts\integration_demo.py
```

The checked-in JavaScript is ready to run. To edit the UI, use `npm ci`, then `npm run build:ui`. TypeScript output goes to scratch before replacing the served JS.

## Upstream components

Weights and binaries are kept separately from this repository. Their upstream licenses remain applicable. Model cards: [Qwen3 8B](https://huggingface.co/Qwen/Qwen3-8B), [Qwen3-VL 4B](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct), [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M), [FLUX.2 klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B). The installed quantized/split distributions and exact download locations are recorded in `dependencies.json`. Source projects: [llama.cpp](https://github.com/ggml-org/llama.cpp), [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [FFmpeg](https://ffmpeg.org/), [Playwright](https://github.com/microsoft/playwright).
