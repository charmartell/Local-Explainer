import re
import threading
from .models import LocalModels

LABELS = {'af_heart': 'Heart', 'af_bella': 'Bella', 'af_nicole': 'Nicole', 'am_adam': 'Adam', 'am_michael': 'Michael'}

def available(config):
    return [{'id': p.stem, 'name': LABELS.get(p.stem, p.stem[3:].replace('_', ' ').title()),
             'description': 'American English'}
            for p in sorted((config.assets / 'Models' / 'kokoro').glob('a[fm]_*.pt'))
            if re.fullmatch(r'a[fm]_[a-z0-9_]+', p.stem)]

def validate(config, voice):
    if voice not in {v['id'] for v in available(config)}: raise ValueError('Choose an installed local voice')
    return voice

class VoicePreviews:
    def __init__(self, config): self.config = config; self.lock = threading.Lock()

    def sample(self, voice):
        validate(self.config, voice)
        with self.lock:
            folder = self.config.scratch / 'voice-previews' / voice
            result = LocalModels(self.config).speech([{'id': 'sample', 'speech_text':
                'Let us walk through how this works, one step at a time. We will connect the design to the code and explain why each part matters.'}], folder, voice=voice)
            return result[0]['path']
