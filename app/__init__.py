import os
from pathlib import Path
import secrets
from datetime import timedelta
import click
from flask import Flask, render_template
from flask_login import LoginManager
from flask_migrate import Migrate, upgrade
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from .models import db, User

login=LoginManager()
csrf=CSRFProtect()
migrate=Migrate()

@event.listens_for(Engine,'connect')
def sqlite_pragmas(connection, record):
    if type(connection).__module__=='sqlite3':
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=10000')

def create_app(test_config=None):
    app=Flask(__name__)
    data=Path(os.environ.get('TIMBER_DATA_DIR') or os.environ.get('DATA_DIR') or Path(app.root_path).parent/'.local-data').resolve()
    app.config.update(SQLALCHEMY_DATABASE_URI='sqlite:///'+str(data/'timber.db'),SQLALCHEMY_TRACK_MODIFICATIONS=False,
                      SECRET_KEY=os.environ.get('SECRET_KEY'),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('TIMBER_SECURE_COOKIES')=='1',PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
                      MAX_CONTENT_LENGTH=1024*1024,DATA_DIR=str(data),DEBUG=False,
                      UPLOAD_DIR=str(Path(os.environ.get('UPLOAD_DIR',data/'uploads')).resolve()))
    if test_config:app.config.update(test_config)
    if not app.config.get('TESTING'):
        data.mkdir(parents=True,exist_ok=True)
        if not app.config['SECRET_KEY']:
            key_file=data/'session.key'
            try:
                fd=os.open(key_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(32))
            except FileExistsError:pass
            app.config['SECRET_KEY']=key_file.read_text().strip()
        if os.environ.get('TIMBER_ENV')=='production' and len(app.config['SECRET_KEY'])<32:
            raise RuntimeError('Production SECRET_KEY must contain at least 32 characters; check the environment or persistent session.key.')
    db.init_app(app);login.init_app(app);csrf.init_app(app)
    migrate.init_app(app,db,directory=str(Path(app.root_path).parent/'migrations'))
    login.login_view='web.login_view'
    @login.user_loader
    def load_user(user_id):
        try:return db.session.get(User,int(user_id))
        except ValueError:return None
    from .routes import web
    app.register_blueprint(web)
    @app.template_filter('gbp')
    def gbp(value):return '—' if value is None else f'£{value:,.2f}'
    @app.cli.command('init-db')
    def init_db():
        """Upgrade schema and seed missing catalogue rows, without resetting edits."""
        upgrade(directory=str(Path(app.root_path).parent/'migrations'))
        from .seed import seed
        seed();click.echo('Database ready. Visit http://127.0.0.1:2112 to create the first administrator.')
    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    def error_page(error):return render_template('error.html',error=error),error.code
    return app
