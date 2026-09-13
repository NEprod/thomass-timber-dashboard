import json
from pathlib import Path
import pytest
from app import create_app
from app.models import db
from app.seed import seed

@pytest.fixture
def seed_data():
    return json.loads((Path(__file__).parents[1]/'app/data/catalogue.json').read_text())

@pytest.fixture
def catalogue(seed_data):
    return {m['id']:m for m in seed_data['materials']}

@pytest.fixture
def app(tmp_path):
    app=create_app({'TESTING':True,'SECRET_KEY':'test-only-key','WTF_CSRF_ENABLED':False,
                    'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'test.db')})
    with app.app_context():
        db.create_all();seed()
    yield app
    with app.app_context():
        db.session.remove();db.engine.dispose()

@pytest.fixture
def client(app):return app.test_client()

@pytest.fixture
def signed_in(client):
    response=client.post('/setup',data={'email':'test@example.test','password':'a-test-password-123','confirm_password':'a-test-password-123'})
    assert response.status_code==302
    return client
