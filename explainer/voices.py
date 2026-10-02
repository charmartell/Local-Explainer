import re
import shutil
from .models import LocalModels

LABELS = {'af_heart': 'Heart', 'af_bella': 'Bella', 'af_nicole': 'Nicole', 'am_adam': 'Adam', 'am_michael': 'Michael'}
SAMPLE_TEXT = 'Let us walk through how this works, one step at a time. We will connect the design to the code and explain why each part matters.'

def available(config):
    return [{'id': p.stem, 'name': LABELS.get(p.stem, p.stem[3:].replace('_', ' ').title()),
             'description': 'American English'}
            for p in sorted((config.assets / 'Models' / 'kokoro').glob('a[fm]_*.pt'))
            if re.fullmatch(r'a[fm]_[a-z0-9_]+', p.stem)]

def validate(config, voice):
    if voice not in {v['id'] for v in available(config)}: raise ValueError('Choose an installed local voice')
    return voice

class VoicePreviews:
    def __init__(self, config): self.config = config

    def path(self, voice):
        return self.config.assets / 'VoicePreviews' / 'v1' / (voice + '.wav')

    def sample(self, voice):
        validate(self.config, voice)
        path = self.path(voice)
        if not path.is_file():
            raise ValueError('This voice sample is not installed. Run python -m explainer.voices during setup.')
        return path

    def prepare(self):
        """Build fixed samples during installation, never during playback."""
        for voice in available(self.config):
            voice_id = voice['id']; path = self.path(voice_id)
            if path.is_file(): continue
            folder = self.config.scratch / 'voice-previews' / voice_id
            result = LocalModels(self.config).speech([{'id':'sample','speech_text':SAMPLE_TEXT}],folder,voice=voice_id)
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary = path.with_suffix('.tmp.wav')
            shutil.copyfile(result[0]['path'],temporary)
            temporary.replace(path)
            print('Voice sample ready:',voice['name'],flush=True)


if __name__ == '__main__':
    from .config import settings
    VoicePreviews(settings()).prepare()
