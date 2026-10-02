---
name: local-explainer
description: Create source-grounded narrated learning videos locally from a concept, repository, design, or technical process. Use for educational video generation or changes to an existing Local Explainer lesson, not ordinary explanations in chat.
---

# Local Explainer

The application is installed at `C:\Dev\Local-Explainer`. Its independent browser UI runs at `http://127.0.0.1:8090`. Generation uses local language, vision, image, and speech models. Codex coordinates the application; the browser application also works without Codex.

## Start and inspect

Run `C:\Dev\Local-Explainer\Start-Local-Explainer.ps1` to start the application and open its UI. Use `scripts\invoke.ps1` in this skill for structured localhost API operations. It returns JSON immediately; planning and production run asynchronously. Check status while continuing useful work. Preserve the application's single GPU queue.

## Create a lesson

Prepare a request JSON under `C:\Dev\_scratch\Local-Explainer\requests` with `topic`, `inputs` (absolute file/folder paths or reference URLs), `goal`, `audience`, `minutes` (1–20), and `mode` (`offline` or `research`). Default to offline for local sources; choose research when the user requests outside research or a concept needs references. Research mode sends the topic as a search query and fetches public pages. Inference stays local.

Call `invoke.ps1 -Action plan -RequestFile <absolute path>`. Poll status until `awaiting_approval` or `failed`. Present only the brief outline, visual direction, and material gaps. The user can review and approve in the application.

Do not approve a real lesson automatically. Approval applies to the concrete outline hash the user reviewed. After explicit approval in chat, call `-Action approve -Job <id> -OutlineHash <reviewed hash>`, then `-Action produce -Job <id>`. A request to create a video authorizes source analysis and an outline; the user's requested workflow includes this review before production. Never bypass it with an implementation-test approval.

On completion, show the MP4, illustrated transcript, and source links using the returned absolute artifact paths. Explain material source gaps; do not imply that model review proves correctness. Keep implementation details out of the lesson itself.

## Changes and recovery

For an explicitly requested change to one scene of a completed lesson, use `-Action revise -Job <id> -SceneId <id> -Instruction <change>`. This preserves the approved chapter structure and regenerates the selected scene. Other scenes reuse saved work. Changes to the whole lesson omit SceneId and require review of the revised outline.

Use `cancel` to pause generation and `resume` to recover saved stages. Do not launch a second CLI inference job against the running UI. No cloud fallback or upload is configured. Source repositories remain read-only; model logs and intermediate media belong under the application scratch directory.
