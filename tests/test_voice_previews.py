import wave
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from explainer.config import Settings
from explainer.api import make_app
from explainer.voices import VoicePreviews


def test_preview_serves_installed_audio_without_inference(tmp_path):
    config=Settings(assets=tmp_path/'assets',scratch=tmp_path/'scratch',builds=tmp_path/'builds')
    config.prepare()
    voices=config.assets/'Models'/'kokoro';voices.mkdir(parents=True)
    (voices/'af_bella.pt').touch()
    previews=VoicePreviews(config)
    with patch('explainer.voices.LocalModels') as models:
        with pytest.raises(ValueError,match='not installed'): previews.sample('af_bella')
        sample=previews.path('af_bella');sample.parent.mkdir(parents=True)
        with wave.open(str(sample),'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(b'\0\0'*2400)
        previews.prepare()
        with TestClient(make_app(config)) as client:
            for method in (client.get,client.post,client.get):
                response=method('/api/voices/af_bella/preview')
                assert response.status_code==200
                assert response.content==sample.read_bytes()
                assert response.headers['content-type']=='audio/wav'
            assert client.get('/api/voices/../../secret/preview').status_code==404
            assert client.get('/api/voices/am_unknown/preview').status_code==409
        models.assert_not_called()
