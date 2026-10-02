import json
from pathlib import Path
from explainer import config


def test_portable_defaults_and_override_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'REPO', tmp_path)
    for key in ('ASSETS', 'SCRATCH', 'BUILDS', 'COMFY_REPO'):
        monkeypatch.delenv('LOCAL_EXPLAINER_' + key, raising=False)
    assert config.Settings().assets == tmp_path/'data'/'assets'
    assert config.Settings().comfy_repo == tmp_path/'data'/'assets'/'Runtime'/'ComfyUI'
    local_assets = tmp_path/'existing-assets'
    (tmp_path/'.local-paths.json').write_text(json.dumps({'assets': str(local_assets)}))
    assert config.Settings().assets == local_assets
    assert config.Settings().comfy_repo == local_assets/'Runtime'/'ComfyUI'
    override = tmp_path/'override'
    monkeypatch.setenv('LOCAL_EXPLAINER_ASSETS', str(override))
    assert config.Settings().assets == override
    assert config.Settings().comfy_repo == override/'Runtime'/'ComfyUI'
    monkeypatch.setenv('LOCAL_EXPLAINER_COMFY_REPO', str(tmp_path/'external-comfy'))
    assert config.Settings().comfy_repo == tmp_path/'external-comfy'
