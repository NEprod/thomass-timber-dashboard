"""Migrate once before replacing this process with the production WSGI server."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    os.umask(0o077)
    data = Path(os.environ.get('TIMBER_DATA_DIR') or os.environ.get('DATA_DIR', '/data')).resolve()
    uploads = Path(os.environ.get('UPLOAD_DIR', '/uploads')).resolve()
    os.environ['TIMBER_DATA_DIR'] = str(data)
    os.environ['UPLOAD_DIR'] = str(uploads)
    os.environ['TIMBER_ENV'] = 'production'
    os.environ['FLASK_DEBUG'] = '0'
    for path in (data, uploads):
        path.mkdir(parents=True, exist_ok=True)
        if not os.access(path, os.W_OK | os.X_OK):
            raise PermissionError(f'{path} must be writable by container UID {os.getuid()} / GID {os.getgid()}')
    os.chdir(Path(__file__).resolve().parents[1])
    print('Applying database migrations and seeding missing configuration...', flush=True)
    subprocess.run([sys.executable, '-m', 'flask', '--app', 'app', 'init-db'], check=True)
    print('Database ready; starting Gunicorn.', flush=True)
    os.execvp('gunicorn', ['gunicorn', '--config', 'docker/gunicorn.conf.py', 'app:create_app()'])


if __name__ == '__main__':
    main()
