const app = document.querySelector('#app');
let jobs = [], selected = localStorage.getItem('selected-lesson'), health = {}, voices = [], busy = false, lastStatus = '', library = { lessons: [] }, view = localStorage.getItem('studio-view') || 'lesson';
let search = '', filter = 'all', sort = 'updated', picks = new Set(), voiceURL = '';
let draft;
try {
    draft = JSON.parse(localStorage.getItem('composer-draft') || '{}');
}
catch {
    draft = {};
}
draft = { topic: '', inputs: '', goal: 'Understand the mechanism and its tradeoffs', audience: 'Curious builder; explain unfamiliar terms', mode: 'offline', minutes: 8, voice: 'af_heart', kind: 'lesson', explanation_styles: [], visual_preferences: [], visual_direction: '', ...draft };
const explanationStyles = [['step_by_step', 'Step by step'], ['analogy', 'Everyday analogies'], ['worked_example', 'Worked examples'], ['why_it_works', 'Why it works'], ['tradeoffs', 'Tradeoffs & pitfalls'], ['recap', 'Recap & repetition']];
const visualPreferences = [['diagram', 'Labeled diagrams'], ['sequence', 'Process flows'], ['state', 'State changes'], ['code', 'Code highlights'], ['illustration', 'Illustrated examples'], ['comparison', 'Comparison tables'], ['recap', 'Summary cards']];
function presets(name, options) { return `<div class="preset-tags">${options.map(([value, label]) => `<label class="preset-tag"><input type="checkbox" name="${name}" value="${value}" ${(draft[name] || []).includes(value) ? 'checked' : ''}><span>${esc(label)}</span></label>`).join('')}</div>`; }
const esc = (x) => String(x ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const bytes = (n) => { if (!n)
    return '0 B'; const i = Math.min(3, Math.floor(Math.log(n) / Math.log(1024))); return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${['B', 'KB', 'MB', 'GB'][i]}`; };
const date = (value) => new Date(value).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
const title = (job) => job.outline?.title || job.request.topic;
const category = (job) => job.label === 'lesson' ? (job.status === 'complete' ? 'video' : 'draft') : job.label === 'demo' || job.request.kind === 'demo' || job.approval?.actor === 'implementation_test' ? 'demo' : job.status === 'complete' ? 'video' : 'draft';
const status = (job) => job.storage_state === 'offloaded' ? 'offloaded' : job.status === 'awaiting_approval' ? 'outline ready' : job.status.replaceAll('_', ' ');
async function api(path, body) { const r = await fetch(path, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }); const data = await r.json(); if (!r.ok)
    throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)); return data; }
const artifact = (job, name) => `/api/jobs/${job.id}/artifacts/${encodeURIComponent(name)}`;
function navigate(next, id) { view = next; localStorage.setItem('studio-view', next); if (id) {
    selected = id;
    localStorage.setItem('selected-lesson', id);
} render(); }
function grouped() { const map = new Map(jobs.map(j => [j.id, j])); const groups = new Map(); for (const job of jobs) {
    let root = job, seen = new Set();
    while (root.parent && map.has(root.parent) && !seen.has(root.id)) {
        seen.add(root.id);
        root = map.get(root.parent);
    }
    const members = groups.get(root.id) || [];
    members.push(job);
    groups.set(root.id, members);
} return [...groups.values()].map(members => members.sort((a, b) => (b.revision || 1) - (a.revision || 1) || b.created.localeCompare(a.created))); }
function matches(job, members = [job]) { const demo = members.some(j => category(j) === 'demo'); const cat = demo ? 'demo' : category(job); return (!search || members.some(j => `${title(j)} ${j.request.topic}`.toLowerCase().includes(search.toLowerCase()))) && (filter === 'all' || filter === cat || filter === 'offloaded' && job.storage_state === 'offloaded' || filter === 'active' && members.some(j => ['planning', 'queued', 'producing'].includes(j.status))); }
function ordered(groups) { return groups.sort((a, b) => sort === 'oldest' ? a.at(-1).created.localeCompare(b.at(-1).created) : sort === 'created' ? b.at(-1).created.localeCompare(a.at(-1).created) : b[0].updated.localeCompare(a[0].updated)); }
function sidebarRows() { const groups = ordered(grouped().filter(m => matches(m[0], m))); return groups.map(m => `<div class="lesson-group"><button class="lesson-item ${m.some(j => j.id === selected) && view === 'lesson' ? 'selected' : ''}" data-job="${m[0].id}"><strong>${esc(title(m[0]))}</strong><small>${m.some(j => category(j) === 'demo') ? 'demo' : category(m[0])} · ${esc(status(m[0]))}</small><time title="Updated ${esc(date(m[0].updated))}">${esc(date(m[0].updated))}</time></button>${m.length > 1 ? `<details class="revisions"><summary>${m.length - 1} earlier revision${m.length > 2 ? 's' : ''}</summary>${m.slice(1).map(j => `<button class="lesson-item history" data-job="${j.id}"><strong>Revision ${j.revision || 1} · ${esc(title(j))}</strong><small>${esc(status(j))} · ${esc(date(j.created))}</small></button>`).join('')}</details>` : ''}</div>`).join('') || '<p class="empty">No matching lessons.</p>'; }
function bindJobs() { document.querySelectorAll('[data-job]').forEach(b => b.onclick = () => navigate('lesson', b.dataset.job)); }
function filterChange() { document.querySelector('#lesson-rows').innerHTML = sidebarRows(); bindJobs(); if (view === 'library')
    libraryRows(); }
function shell(content) { app.innerHTML = `<header><div class="brand"><span>▶</span>Local Explainer</div><div class="local"><i class="dot"></i>Production stays on this computer</div></header><main><aside><button class="button primary new" id="new">＋ Composer</button><button class="button library-link" id="library">Library & storage</button><h2>Your lessons</h2><label class="sr-only" for="lesson-search">Search lessons</label><input id="lesson-search" type="search" placeholder="Search lessons…" value="${esc(search)}"><div class="sidebar-controls"><label class="sr-only" for="lesson-filter">Filter lessons</label><select id="lesson-filter">${[['all', 'All lessons'], ['draft', 'Drafts'], ['video', 'Videos'], ['demo', 'Demos'], ['active', 'In progress'], ['offloaded', 'Offloaded']].map(([v, t]) => `<option value="${v}" ${v === filter ? 'selected' : ''}>${t}</option>`).join('')}</select><label class="sr-only" for="lesson-sort">Sort lessons</label><select id="lesson-sort">${[['updated', 'Recently updated'], ['created', 'Newest created'], ['oldest', 'Oldest created']].map(([v, t]) => `<option value="${v}" ${v === sort ? 'selected' : ''}>${t}</option>`).join('')}</select></div><div id="lesson-rows">${sidebarRows()}</div></aside><section class="workspace">${content}</section></main>`; document.querySelector('#new').addEventListener('click', () => navigate('composer')); document.querySelector('#library').addEventListener('click', () => action(async () => { library = await api('/api/library'); navigate('library'); })); document.querySelector('#lesson-search').oninput = e => { search = e.target.value; filterChange(); }; document.querySelector('#lesson-filter').onchange = e => { filter = e.target.value; filterChange(); }; document.querySelector('#lesson-sort').onchange = e => { sort = e.target.value; filterChange(); }; bindJobs(); }
function render() { if (view === 'library') {
    storage();
    return;
} const job = jobs.find(j => j.id === selected); if (view === 'composer' || !job) {
    composer();
    return;
} if (job.storage_state === 'offloaded') {
    offloaded(job);
    return;
} if (job.status === 'awaiting_approval') {
    review(job);
    return;
} if (job.status === 'complete') {
    complete(job);
    return;
} progress(job); }
function remember() { for (const name of ['topic', 'inputs', 'goal', 'audience', 'mode', 'minutes', 'voice', 'kind', 'visual_direction']) {
    const el = document.querySelector(`[name="${name}"]`);
    if (el)
        draft[name] = name === 'minutes' ? Number(el.value) : el.value;
} for (const name of ['explanation_styles', 'visual_preferences']) {
    draft[name] = [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(el => el.value);
} localStorage.setItem('composer-draft', JSON.stringify(draft)); }
function addSources(paths) { const current = String(draft.inputs).split('\n').map((s) => s.trim()).filter(Boolean); const next = [...new Set([...current, ...paths])]; if (next.length > 20)
    throw Error('Choose up to 20 source files or folders; a repository counts as one source.'); draft.inputs = next.join('\n'); document.querySelector('#inputs').value = draft.inputs; remember(); document.querySelector('#source-status').textContent = `${paths.length} source${paths.length === 1 ? '' : 's'} added.`; }
function depth() { const m = Number(document.querySelector('#minutes').value); document.querySelector('#depth-value').textContent = `${m <= 4 ? 'Shortform' : m <= 10 ? 'Standard' : 'Longform'} · about ${m} minute${m === 1 ? '' : 's'}`; document.querySelector('#depth-hint').textContent = m <= 4 ? 'The core idea and one clear example.' : m <= 10 ? 'Explain the mechanism, connections, and practical tradeoffs.' : 'More steps, worked examples, and supported failure and recovery paths.'; remember(); }
function composer() { shell(`<p class="eyebrow">Composer</p><h1>Turn a subject into a lesson.</h1><p class="lead">Start with a concept, repository, design, or process. Choose your sources and style, then review a brief outline.</p><form id="request" class="card form"><div class="field"><label for="topic">Title of the video</label><input id="topic" name="topic" required minlength="3" maxlength="500" value="${esc(draft.topic)}" placeholder="How Tavern publishes and installs updates" aria-describedby="title-hint"><p class="hint" id="title-hint">A short name for your video. Put your questions and detailed instructions in the explanation below.</p></div><div class="dropzone" id="dropzone" tabindex="0" aria-label="Drop lesson sources"><strong>Drop files, a folder, or reference links here</strong><p class="hint">Local copies only. Choose a repository to read its original files and Git context.</p><div class="actions"><button type="button" class="button" id="pick-repo">Choose repository…</button><button type="button" class="button" id="pick-files">Choose files…</button></div><p class="hint" id="source-status" role="status"></p></div><details class="source-paths" open><summary>Source paths and reference URLs</summary><label class="sr-only" for="inputs">Source paths or reference URLs</label><textarea id="inputs" name="inputs" placeholder="One absolute path or reference URL per line">${esc(draft.inputs)}</textarea><p class="hint">Up to 20 sources. For large repos, add the relevant module or files as well.</p></details><div class="field"><label for="goal">What would you like explained?</label><textarea id="goal" name="goal" maxlength="2000" placeholder="Describe your questions, what confuses you, and what you want to be able to do.">${esc(draft.goal)}</textarea><p class="hint">Choose any explanation styles that help you learn. Combine them with your own instructions.</p><fieldset class="preferences"><legend>Explanation styles</legend>${presets('explanation_styles', explanationStyles)}</fieldset></div><fieldset class="preferences visual-preferences"><legend>How should the lesson show the idea?</legend><p class="hint">Pick your preferred visual tools. Leave these unchecked to let the lesson choose.</p>${presets('visual_preferences', visualPreferences)}<div class="field"><label for="visual_direction">Your visual & learning directions</label><textarea id="visual_direction" name="visual_direction" maxlength="2000" placeholder="For example: follow one example from start to finish, label each arrow, show before and after, and repeat the key idea in a final diagram.">${esc(draft.visual_direction)}</textarea><div class="actions visual-examples">${[['Label the arrows', 'Use descriptive arrow labels to explain why each connection exists.'], ['One running example', 'Follow one concrete example through the lesson, with intermediate steps.'], ['Before & after', 'Compare before and after using the same entities and consistent labels.'], ['Slow it down', 'Explain unfamiliar terms before using them and reveal one step at a time.']].map(([label, text]) => `<button type="button" class="button" data-direction="${esc(text)}">${label}</button>`).join('')}</div></div><p class="hint">Local capabilities: labeled diagrams, flows, comparison tables, code highlights, and generated still illustrations with narration and timed emphasis. Image detail and consistency vary; interactive exercises and generated motion footage are not available. Preferences guide generation; review the planned approach in the outline.</p></fieldset><div class="field"><label for="audience">Audience</label><input id="audience" name="audience" maxlength="500" value="${esc(draft.audience)}"></div><div class="field"><label for="minutes">Explanation depth · shortform to longform</label><div class="range-labels"><span>Shortform</span><output id="depth-value"></output><span>Longform</span></div><input type="range" id="minutes" name="minutes" min="1" max="20" value="${draft.minutes}"><p class="hint" id="depth-hint"></p></div><div class="row"><div class="field"><label for="voice">Narrator voice</label><select id="voice" name="voice">${voices.map(v => `<option value="${esc(v.id)}" ${v.id === draft.voice ? 'selected' : ''}>${esc(v.name)} · ${esc(v.description)}</option>`).join('')}</select><button type="button" class="button voice-preview" id="preview-voice">Preview voice</button><audio id="voice-audio" controls hidden></audio></div><div class="field"><label for="mode">Sources and research</label><select id="mode" name="mode"><option value="offline" ${draft.mode === 'offline' ? 'selected' : ''}>Offline · local and cached sources</option><option value="research" ${draft.mode === 'research' ? 'selected' : ''}>Local models + web research</option></select><p class="hint">Research fetches public references. Inference and production remain local.</p><label for="kind" class="kind-label">Library category</label><select id="kind" name="kind"><option value="lesson" ${draft.kind === 'lesson' ? 'selected' : ''}>Lesson</option><option value="demo" ${draft.kind === 'demo' ? 'selected' : ''}>Demo / test</option></select></div></div><div id="form-error" role="alert"></div><div class="actions"><button class="button primary" type="submit">Prepare lesson outline →</button><span class="hint">You review before video production.</span></div></form><div id="action-error" role="alert"></div>`); depth(); document.querySelectorAll('[data-direction]').forEach(button => button.onclick = () => { const field = document.querySelector('#visual_direction'); const addition = button.dataset.direction; if (!field.value.includes(addition)) {
    const next = [field.value.trim(), addition].filter(Boolean).join('\n');
    if (next.length > 2000) {
        document.querySelector('#form-error').textContent = 'Visual directions can contain up to 2,000 characters.';
        return;
    }
    field.value = next;
    remember();
} field.focus(); }); document.querySelector('#request').addEventListener('input', remember); document.querySelector('#request').addEventListener('change', remember); document.querySelector('#minutes').addEventListener('input', depth); for (const [id, kind] of [['pick-repo', 'folder'], ['pick-files', 'files']])
    document.querySelector(`#${id}`).addEventListener('click', () => sourceAction(async () => { document.querySelector('#source-status').textContent = 'The Windows picker is open…'; const result = await api('/api/picker', { kind }); if (result.paths.length)
        addSources(result.paths);
    else
        document.querySelector('#source-status').textContent = 'Selection canceled.'; })); const zone = document.querySelector('#dropzone'); zone.ondragover = e => { e.preventDefault(); zone.classList.add('dragging'); }; zone.ondragleave = () => zone.classList.remove('dragging'); zone.ondrop = e => { e.preventDefault(); zone.classList.remove('dragging'); sourceAction(() => drop(e.dataTransfer)); }; document.querySelector('#preview-voice').addEventListener('click', () => sourceAction(async () => { const button = document.querySelector('#preview-voice'); button.textContent = 'Preparing local sample…'; try {
    const r = await fetch(`/api/voices/${encodeURIComponent(draft.voice)}/preview`, { method: 'POST' });
    if (!r.ok)
        throw Error((await r.json()).detail);
    if (voiceURL)
        URL.revokeObjectURL(voiceURL);
    voiceURL = URL.createObjectURL(await r.blob());
    const audio = document.querySelector('#voice-audio');
    audio.src = voiceURL;
    audio.hidden = false;
    await audio.play().catch(() => { });
}
finally {
    button.textContent = 'Preview voice';
} })); document.querySelector('#request').onsubmit = e => { e.preventDefault(); remember(); action(async () => { const minutes = Number(draft.minutes); const next = await api('/api/jobs', { ...draft, inputs: String(draft.inputs).split('\n').map(s => s.trim().replace(/^"|"$/g, '')).filter(Boolean), detail_level: minutes <= 4 ? 'shortform' : minutes <= 10 ? 'standard' : 'longform' }); navigate('lesson', next.id); await refresh(true); }); }; }
async function sourceAction(fn) { if (busy)
    return; busy = true; const buttons = [...document.querySelectorAll('#request button')]; buttons.forEach(b => b.disabled = true); try {
    await fn();
}
catch (e) {
    document.querySelector('#form-error').innerHTML = `<p class="notice error">${esc(e.message)}</p>`;
}
finally {
    busy = false;
    buttons.forEach(b => b.disabled = false);
} }
const skip = new Set(['.git', 'node_modules', 'build', 'dist', '.venv', 'venv', '__pycache__', '.next', '.wrangler', 'target', 'vendor']);
const allowed = /\.(md|txt|rst|py|ts|tsx|js|jsx|json|toml|yaml|yml|sql|dart|rs|go|cs|java|c|cpp|h|css|html|xml|sh|ps1|svg|pdf|png|jpe?g|webp)$/i;
async function drop(data) {
    const collected = [];
    let skipped = 0;
    async function entry(node, prefix = '') { if (skip.has(node.name) || node.name.startsWith('.env') || /secret|credentials|private-key/i.test(node.name)) {
        skipped++;
        return;
    } if (node.isDirectory) {
        const reader = node.createReader();
        while (true) {
            const children = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
            if (!children.length)
                break;
            for (const child of children)
                await entry(child, prefix + node.name + '/');
        }
    }
    else {
        const file = await new Promise((resolve, reject) => node.file(resolve, reject));
        if (allowed.test(file.name)) {
            collected.push({ file, name: prefix + file.name });
            if (collected.length > 400)
                throw Error('Use Choose repository for folders with more than 400 source files.');
        }
        else
            skipped++;
    } }
    for (const item of [...data.items]) {
        if (item.kind !== 'file')
            continue;
        const node = item.webkitGetAsEntry?.();
        if (node)
            await entry(node);
        else {
            const file = item.getAsFile();
            if (file && allowed.test(file.name))
                collected.push({ file, name: file.name });
            else
                skipped++;
        }
    }
    if (!collected.length) {
        const text = data.getData('text/uri-list') || data.getData('text/plain');
        if (text.trim()) {
            addSources(text.split(/\r?\n/).filter(s => s.trim() && !s.startsWith('#')).map(s => s.trim().replace(/^"|"$/g, '')));
            return;
        }
        throw Error('No supported files found. Choose repository for a large folder.');
    }
    if (collected.some(x => x.file.size > 10000000) || collected.reduce((n, x) => n + x.file.size, 0) > 100000000)
        throw Error('Drop up to 10 MB per file and 100 MB total, or choose a local path.');
    const batch = await api('/api/sources', {});
    for (let i = 0; i < collected.length; i++) {
        document.querySelector('#source-status').textContent = `Copying locally: ${i + 1}/${collected.length} · ${collected[i].file.name}`;
        const r = await fetch(`/api/sources/${batch.batch}?path=${encodeURIComponent(collected[i].name)}`, { method: 'PUT', headers: { 'Content-Type': 'application/octet-stream' }, body: collected[i].file });
        if (!r.ok)
            throw Error((await r.json()).detail);
    }
    const result = await api(`/api/sources/${batch.batch}/finish`, {});
    addSources(result.paths);
    document.querySelector('#source-status').textContent = `${result.files} file${result.files === 1 ? '' : 's'} copied locally${skipped ? `; ${skipped} unsupported or excluded entries skipped` : ''}.`;
}
function metadata(job) { return `<div class="meta"><span>${esc(category(job))} · revision ${job.revision || 1}</span><span>Created ${esc(date(job.created))}</span><span>Updated ${esc(date(job.updated))}</span>${job.request.voice ? `<span>Voice: ${esc(voices.find(v => v.id === job.request.voice)?.name || job.request.voice)}</span>` : ''}</div>`; }
function review(job) { const o = job.outline; shell(`<p class="eyebrow">Your lesson outline</p><h1>${esc(o.title)}</h1>${metadata(job)}<div class="meta"><span>About ${o.minutes} minutes</span><span>${job.request.mode === 'offline' ? 'Offline' : 'Local with web research'}</span></div><div class="card outline"><p class="outcome">${esc(o.outcome)}</p><p class="hint">${esc(o.assumptions)}</p><ol>${o.beats.map((b) => `<li><strong>${esc(b.title)}</strong><p>${esc(b.focus)}</p></li>`).join('')}</ol><p><strong>Visuals:</strong> ${esc(o.visuals)}</p>${o.gaps?.length ? `<div class="notice">${o.gaps.map(esc).join('<br>')}</div>` : ''}<details><summary>Evidence and source references</summary><div id="sources">Loading source references…</div></details></div><div class="actions"><button class="button primary" id="generate">Generate my video →</button><button class="button" id="adjust">Adjust outline</button><button class="button" id="cancel">Cancel</button></div><p class="hint">The script, visuals, and narration are produced after you approve this outline.</p><div id="action-error" role="alert"></div>`); document.querySelector('#generate').addEventListener('click', () => action(async () => { await api(`/api/jobs/${job.id}/approval`, { outline_hash: o.hash }); await api(`/api/jobs/${job.id}/production`, {}); await refresh(true); })); document.querySelector('#adjust').addEventListener('click', () => adjust(job)); document.querySelector('#cancel').addEventListener('click', () => action(async () => { await api(`/api/jobs/${job.id}/cancel`, {}); await refresh(true); })); api(`/api/jobs/${job.id}/evidence`).then(ev => { const el = document.querySelector('#sources'); if (el)
    el.innerHTML = '<ul>' + ev.sources.map((s) => `<li>${esc(s.title)}<br><small>${esc(s.origin)}</small></li>`).join('') + '</ul>'; }).catch(() => { }); }
function progress(job) { const running = ['queued', 'planning', 'producing'].includes(job.status); shell(`<p class="eyebrow">${running ? 'Preparing your lesson' : 'Lesson saved'}</p><h1>${esc(title(job))}</h1>${metadata(job)}<div class="card"><p class="progress-title" aria-live="polite">${esc(job.stage)}</p><div class="progress"><span style="width:${job.progress}%"></span></div><p class="hint">${job.progress}% · Completed stages are saved.</p>${job.error ? `<div class="notice error">${esc(job.error)}</div>` : ''}<div class="actions">${running ? '<button class="button" id="pause">Pause generation</button>' : '<button class="button primary" id="resume">Resume from saved work</button><button class="button" id="adjust">Adjust lesson</button>'}</div>${job.events.slice(-5).reverse().map(v => `<div class="event">${esc(v.message)}</div>`).join('')}</div><div id="action-error" role="alert"></div>`); document.querySelector('#pause')?.addEventListener('click', () => action(async () => { await api(`/api/jobs/${job.id}/cancel`, {}); await refresh(true); })); document.querySelector('#resume')?.addEventListener('click', () => action(async () => { await api(`/api/jobs/${job.id}/resume`, {}); await refresh(true); })); document.querySelector('#adjust')?.addEventListener('click', () => adjust(job)); }
function complete(job) { shell(`<p class="eyebrow">Ready to watch</p><h1>${esc(title(job))}</h1>${metadata(job)}<div class="meta"><span>${((job.duration || 0) / 60).toFixed(1)} minutes</span><span>1080p · Local production</span></div>${job.storage_state === 'offloaded' ? `<div class="notice">Offloaded to ${esc(job.offload.root)}. Playback reads from that folder.</div>` : ''}<video controls preload="metadata" poster="${artifact(job, (job.scenes?.[0]?.id || 'scene_1_1') + '.jpg')}"><source src="${artifact(job, 'lesson.mp4')}" type="video/mp4"><track kind="captions" label="English" srclang="en" src="${artifact(job, 'captions.vtt')}" default></video><div class="downloads">${(job.chapters || []).map(c => `<button class="button" data-seek="${c.start}">${esc(c.title)}</button>`).join('')}</div><div class="downloads"><a class="button primary" href="${artifact(job, 'lesson.mp4')}" download>Save video</a><a class="button" href="${artifact(job, 'transcript.html')}" target="_blank">Illustrated transcript</a><a class="button" href="${artifact(job, 'sources.html')}" target="_blank">Sources</a><a class="button" href="${artifact(job, 'captions.srt')}" download>Captions</a>${job.storage_state === 'offloaded' ? '<button class="button" id="restore">Restore for editing</button>' : '<button class="button" id="adjust">Make an adjustment</button>'}</div><p class="hint file-path">Files: ${esc(job.artifacts['lesson.mp4'])}</p><details><summary>Production report</summary><a href="${artifact(job, 'quality-report.json')}" target="_blank">Open verification details</a></details><div id="action-error" role="alert"></div>`); document.querySelector('#adjust')?.addEventListener('click', () => adjust(job)); document.querySelector('#restore')?.addEventListener('click', () => restore(job.id)); document.querySelectorAll('[data-seek]').forEach(b => b.onclick = () => { const v = document.querySelector('video'); v.currentTime = Number(b.dataset.seek); v.play(); }); }
function offloaded(job) { if (job.status === 'complete') {
    complete(job);
    return;
} shell(`<p class="eyebrow">Offloaded lesson</p><h1>${esc(title(job))}</h1>${metadata(job)}<div class="card"><p>This draft is stored in your chosen archive folder.</p><p class="hint file-path">${esc(job.offload?.root)}</p><button class="button primary" id="restore">Restore to continue</button></div><div id="action-error" role="alert"></div>`); document.querySelector('#restore').addEventListener('click', () => restore(job.id)); }
function restore(id) { action(async () => { await api(`/api/jobs/${id}/restore`, {}); library = await api('/api/library'); await refresh(true); }); }
function adjust(job) { const dialog = document.createElement('dialog'); const hasScenes = job.status === 'complete' && job.scenes?.length; dialog.innerHTML = `<form><h2>Adjust this lesson</h2>${hasScenes ? `<div class="field"><label for="scope">What should change?</label><select id="scope"><option value="">Whole lesson · review a fresh outline</option>${job.scenes.map(s => `<option value="${esc(s.id)}">${esc(s.title)}</option>`).join('')}</select></div>` : ''}<p class="hint" id="revision-hint">Describe your change. A whole-lesson revision stays grouped with this lesson.</p><label class="sr-only" for="revision">Your adjustment</label><textarea id="revision" required minlength="3" maxlength="2000" placeholder="Explain this in simpler terms, with a concrete example"></textarea><div class="actions"><button class="button primary" id="revise-button">Prepare revised outline</button><button class="button" type="button" id="close-dialog">Cancel</button></div></form>`; document.body.append(dialog); dialog.showModal(); dialog.querySelector('#scope')?.addEventListener('change', e => { const scoped = e.target.value; dialog.querySelector('#revision-hint').textContent = scoped ? 'Regenerate this scene within the approved lesson. Other scenes reuse saved production.' : 'Review a fresh outline for whole-lesson changes.'; dialog.querySelector('#revise-button').textContent = scoped ? 'Regenerate this scene' : 'Prepare revised outline'; }); dialog.querySelector('#close-dialog').addEventListener('click', () => dialog.close()); dialog.addEventListener('close', () => dialog.remove()); dialog.querySelector('form').onsubmit = e => { e.preventDefault(); const instruction = dialog.querySelector('textarea').value, scene_id = dialog.querySelector('#scope')?.value || null; dialog.close(); action(async () => { const next = await api(`/api/jobs/${job.id}/revisions`, { instruction, scene_id }); navigate('lesson', next.id); await refresh(true); }); }; }
function storage() { shell(`<p class="eyebrow">Library & storage</p><h1>Keep your library manageable.</h1><p class="lead">Select lessons to offload or delete. A selected lesson includes its earlier revisions, source snapshots, working media, and video package.</p><div class="storage-stats"><div><strong>${bytes(library.local_bytes || 0)}</strong><span>Lessons and working media</span></div><div><strong>${bytes(library.free_bytes || 0)}</strong><span>Free on the working drive</span></div><div><strong>${bytes(library.source_bytes || 0)}</strong><span>Dropped source copies</span></div></div><div class="actions storage-actions"><button class="button" id="select-visible">Select visible</button><button class="button" id="clear-selection">Clear</button><button class="button primary" id="offload-selected">Offload selected…</button><button class="button danger" id="delete-selected">Delete selected…</button><button class="button" id="refresh-storage">Refresh sizes</button><span id="selection-count" class="hint"></span></div><div id="action-error" role="alert"></div><div id="storage-rows"></div><p class="hint">Model weights and runtimes are separate from lesson storage. Offload to another drive to free space on this drive. Source repositories are never removed.</p>`); libraryRows(); document.querySelector('#select-visible').addEventListener('click', () => { for (const row of visibleLibrary())
    if (!row.active)
        picks.add(row.root_id); libraryRows(); }); document.querySelector('#clear-selection').addEventListener('click', () => { picks.clear(); libraryRows(); }); document.querySelector('#refresh-storage').addEventListener('click', () => action(async () => { library = await api('/api/library'); render(); })); document.querySelector('#offload-selected').addEventListener('click', () => manage('offload')); document.querySelector('#delete-selected').addEventListener('click', () => manage('delete')); }
function visibleLibrary() { const visible = new Set(grouped().filter(m => matches(m[0], m)).map(m => m[0].id)); return library.lessons.filter((r) => visible.has(r.id)).sort((a, b) => sort === 'oldest' ? a.created.localeCompare(b.created) : sort === 'created' ? b.created.localeCompare(a.created) : b.updated.localeCompare(a.updated)); }
function selectedRows() { return library.lessons.filter((r) => picks.has(r.root_id)); }
function libraryRows() { const el = document.querySelector('#storage-rows'); if (!el)
    return; el.innerHTML = visibleLibrary().map((row) => `<article class="storage-row"><input type="checkbox" data-select="${esc(row.root_id)}" aria-label="Select ${esc(row.title)}" ${picks.has(row.root_id) ? 'checked' : ''} ${row.active ? 'disabled' : ''}><div class="storage-title"><button data-job="${esc(row.id)}">${esc(row.title)}</button><p>${esc(row.category)} · ${esc(row.offloaded ? 'offloaded' : row.status.replaceAll('_', ' '))} · ${row.revision_count} version${row.revision_count === 1 ? '' : 's'}</p><time>Created ${esc(date(row.created))}<br>Updated ${esc(date(row.updated))}</time>${row.archive_unavailable ? '<p class="error-text">Archive unavailable; reconnect its drive.</p>' : ''}</div><div class="storage-size"><strong>${bytes(row.bytes)}</strong><small>local${row.offloaded ? ` · ${bytes(row.archive_bytes)} archived` : ''}</small>${row.offloaded ? `<button class="button small" data-restore="${row.id}" ${row.archive_unavailable ? 'disabled' : ''}>Restore</button>` : ''}<button class="button small" data-label="${row.root_id}" data-kind="${row.category === 'demo' ? 'lesson' : 'demo'}">${row.category === 'demo' ? 'Mark as lesson' : 'Mark as demo'}</button></div></article>`).join('') || '<p class="empty">No matching lessons. Change the filters or create one in the composer.</p>'; bindJobs(); el.querySelectorAll('[data-select]').forEach(box => box.onchange = () => { if (box.checked)
    picks.add(box.dataset.select);
else
    picks.delete(box.dataset.select); selectionCount(); }); el.querySelectorAll('[data-restore]').forEach(b => b.onclick = () => restore(b.dataset.restore)); el.querySelectorAll('[data-label]').forEach(b => b.onclick = () => action(async () => { const row = library.lessons.find((r) => r.root_id === b.dataset.label); for (const id of row.ids)
    await api(`/api/jobs/${id}/label`, { kind: b.dataset.kind }); library = await api('/api/library'); await refresh(true); })); selectionCount(); }
function selectionCount() { const rows = selectedRows(), count = document.querySelector('#selection-count'); if (count)
    count.textContent = `${rows.length} lesson${rows.length === 1 ? '' : 's'} · ${bytes(rows.reduce((n, r) => n + r.bytes, 0))} local selected`; const del = document.querySelector('#delete-selected'), off = document.querySelector('#offload-selected'); if (del)
    del.disabled = !rows.length || rows.some((r) => r.active); if (off)
    off.disabled = !rows.length || rows.some((r) => r.active || r.offloaded); }
function manage(kind) { action(async () => { const rows = selectedRows(); if (!rows.length)
    return; let destination; if (kind === 'offload') {
    const result = await api('/api/picker', { kind: 'folder' });
    if (!result.paths.length)
        return;
    destination = result.paths[0];
} const preview = await api('/api/storage/preview', { ids: rows.flatMap((r) => r.ids), action: kind, destination }); const dialog = document.createElement('dialog'); dialog.innerHTML = `<h2>${kind === 'delete' ? 'Permanently delete selected lessons?' : 'Offload selected lessons?'}</h2><p>${rows.length} lessons, ${preview.versions} versions · ${bytes(preview.bytes)} local${preview.archive_bytes ? ` and ${bytes(preview.archive_bytes)} archived` : ''}.</p><ul>${rows.map((r) => `<li>${esc(r.title)}</li>`).join('')}</ul><p>${kind === 'delete' ? 'This removes the selected source snapshots, outlines, working files, video packages, and any offloaded copies. It cannot be undone. Original source repositories and files remain untouched.' : `Files will be copied to <strong>${esc(destination)}</strong>, verified, then removed from application storage. You can restore them later. Copies on the same drive do not free space on that drive.`}</p><label class="confirm-label"><input id="storage-confirm" type="checkbox"> ${kind === 'delete' ? 'I understand these selected lessons will be permanently deleted.' : 'Move these selected lessons to the verified archive.'}</label><div id="storage-error" role="alert"></div><div class="actions"><button class="button ${kind === 'delete' ? 'danger' : 'primary'}" id="execute-storage" disabled>${kind === 'delete' ? 'Permanently delete' : 'Offload and verify'}</button><button class="button" id="cancel-storage">Cancel</button></div>`; document.body.append(dialog); dialog.showModal(); const button = dialog.querySelector('#execute-storage'); dialog.querySelector('#storage-confirm').onchange = e => button.disabled = !e.target.checked; dialog.querySelector('#cancel-storage').addEventListener('click', () => dialog.close()); dialog.addEventListener('close', () => dialog.remove()); button.onclick = async () => { button.disabled = true; dialog.querySelector('#cancel-storage').disabled = true; dialog.querySelector('#storage-confirm').disabled = true; button.textContent = kind === 'delete' ? 'Deleting…' : 'Copying and verifying…'; try {
    const result = await api('/api/storage/execute', { token: preview.token, confirmation: kind === 'delete' ? 'DELETE' : 'OFFLOAD' });
    library = await api('/api/library');
    picks.clear();
    await refresh(true);
    const errors = result.results.filter((r) => !r.ok);
    if (errors.length)
        throw Error(errors.map((r) => r.error).join('; '));
    dialog.close();
}
catch (e) {
    dialog.querySelector('#storage-error').innerHTML = `<p class="notice error">${esc(e.message)} Refresh the library before retrying.</p>`;
    dialog.querySelector('#cancel-storage').disabled = false;
} }; }); }
async function action(fn) { if (busy)
    return; busy = true; try {
    await fn();
}
catch (e) {
    const el = document.querySelector('#action-error') || document.querySelector('#form-error');
    if (el)
        el.innerHTML = `<p class="notice error">${esc(e.message)}</p>`;
}
finally {
    busy = false;
} }
async function refresh(force = false) { jobs = await api('/api/jobs'); const marker = JSON.stringify(jobs.map(j => [j.id, j.status, j.stage, j.progress, j.updated, j.outline?.hash, j.storage_state, j.label])); if (force || marker !== lastStatus) {
    lastStatus = marker;
    if (force || view === 'lesson')
        render();
    else {
        document.querySelector('#lesson-rows').innerHTML = sidebarRows();
        bindJobs();
    }
} }
async function init() { try {
    health = await api('/api/health');
    voices = (await api('/api/voices')).voices;
    if (!voices.some(v => v.id === draft.voice))
        draft.voice = voices[0]?.id || 'af_heart';
    library = await api('/api/library');
    await refresh(true);
    setInterval(() => refresh().catch(() => { }), 2000);
}
catch (e) {
    app.innerHTML = '<p class="notice error">' + esc(e.message) + '</p>';
} }
init();
export {};
