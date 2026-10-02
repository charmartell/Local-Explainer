from dataclasses import dataclass, field
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

def storage_path(name):
    variables = {'assets': 'ASSETS', 'scratch': 'SCRATCH', 'builds': 'BUILDS', 'comfy_repo': 'COMFY_REPO'}
    override = os.environ.get('LOCAL_EXPLAINER_' + variables[name])
    if override:
        return Path(override).expanduser().resolve()
    local_file = REPO / '.local-paths.json'
    local = json.loads(local_file.read_text(encoding='utf-8-sig')) if local_file.exists() else {}
    if name in local:
        return Path(local[name]).expanduser().resolve()
    defaults = {'assets': REPO/'data'/'assets', 'scratch': REPO/'data'/'scratch',
                'builds': REPO/'data'/'builds', 'comfy_repo': REPO/'data'/'assets'/'Runtime'/'ComfyUI'}
    if name == 'comfy_repo':
        return storage_path('assets')/'Runtime'/'ComfyUI'
    return defaults[name]

@dataclass
class Settings:
    assets: Path = field(default_factory=lambda: storage_path("assets"))
    scratch: Path = field(default_factory=lambda: storage_path("scratch"))
    builds: Path = field(default_factory=lambda: storage_path("builds"))
    llama_url: str = 'http://127.0.0.1:8091'
    comfy_url: str = 'http://127.0.0.1:8092'
    comfy_repo: Path = field(default_factory=lambda: storage_path("comfy_repo"))
    voice: str = 'af_heart'
    search_url: str = ''

    @property
    def lessons(self): return self.assets / 'Lessons'
    @property
    def python(self): return self.assets / 'Runtime' / 'inference' / 'Scripts' / 'python.exe'
    @property
    def model(self): return self.assets / 'Models' / 'llm' / 'Qwen3-8B-Q4_K_M.gguf'
    @property
    def llama(self):
        matches = list((self.assets/'Runtime'/'llama').rglob('llama-server.exe'))
        return matches[0] if matches else self.assets/'Runtime'/'llama'/'llama-server.exe'

    def prepare(self):
        for path in (self.assets, self.scratch, self.builds, self.lessons, self.assets/'References'):
            path.mkdir(parents=True, exist_ok=True)
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(self.assets/'Runtime'/'browsers')

def settings():
    s = Settings()
    config = s.assets/'config.json'
    if config.exists():
        data = json.loads(config.read_text(encoding='utf-8'))
        for key in ('llama_url', 'comfy_url', 'voice', 'search_url'):
            if key in data: setattr(s, key, data[key])
    s.prepare()
    return s
