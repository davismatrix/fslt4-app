from pathlib import Path

import config


def test_env_loaded_from_backend_root_and_preserves_exports(tmp_path, monkeypatch):
    backend = tmp_path / 'backend'
    backend.mkdir()
    (backend / '.env').write_text('CHURCH_NAME="Test Church"\nSMTP_PASSWORD="secret # with spaces"\n')
    monkeypatch.setattr(config, '__file__', str(backend / 'config.py'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('CHURCH_NAME', 'Exported Church')
    monkeypatch.delenv('SMTP_PASSWORD', raising=False)
    assert config.load_backend_env()
    import os
    assert os.environ['CHURCH_NAME'] == 'Exported Church'
    assert os.environ['SMTP_PASSWORD'] == 'secret # with spaces'
