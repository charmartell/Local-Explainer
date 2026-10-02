from dataclasses import dataclass
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

@dataclass
class Settings:
    assets: Path = Path(os.environ.get('LOCAL_EXPLAINER_ASSETS', r'C:\Dev\_assets\Local-Explainer'))
    scratch: Path = Path(os.environ.get('LOCAL_EXPLAINER_SCRATCH', r'C:\Dev\_scratch\Local-Explainer'))
    builds: Path = Path(os.environ.get('LOCAL_EXPLAINER_BUILDS', r'C:\Dev\_builds\Local-Explainer'))
    llama_url: str = 'http://127.0.0.1:8091'
    comfy_url: str = 'http://127.0.0.1:8092'
    comfy_repo: Path = Path(r'C:\Dev\ComfyUI-Local-Explainer')
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
