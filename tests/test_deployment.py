import pytest
from app import create_app


def test_health_does_not_require_database_or_admin(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test',
                      'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'empty.db')})
    response = app.test_client().get('/health')
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}
    assert not (tmp_path / 'empty.db').exists()


def test_production_paths_key_and_debug_survive_restart(tmp_path, monkeypatch):
    monkeypatch.delenv('TIMBER_DATA_DIR', raising=False)
    monkeypatch.delenv('SECRET_KEY', raising=False)
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('TIMBER_ENV', 'production')
    monkeypatch.setenv('FLASK_DEBUG', '1')
    first = create_app()
    second = create_app()
    assert not first.debug
    assert first.secret_key == second.secret_key
    assert len(first.secret_key) == 64
    assert (tmp_path / 'data/session.key').stat().st_mode & 0o777 == 0o600
    assert first.config['UPLOAD_DIR'] == str(tmp_path / 'uploads')
    assert first.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///' + str(tmp_path / 'data/timber.db')
    monkeypatch.setenv('SECRET_KEY', 'too-short')
    with pytest.raises(RuntimeError, match='at least 32'):
        create_app()
