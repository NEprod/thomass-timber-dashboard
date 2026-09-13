"""Explicit Docker acceptance test; not collected by pytest.

Uses disposable volumes/containers only, including Unraid's non-root UID/GID.
Run: python tests/container_smoke.py IMAGE [HOST_PORT]
"""
import http.cookiejar
import json
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def main():
    image = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else '2112'
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', int(port)))  # fail before touching any installation on an occupied port
    name = 'timber-smoke-' + uuid.uuid4().hex[:10]
    volumes = [name + '-data', name + '-uploads']
    mounts = ['--mount', f'type=volume,source={volumes[0]},target=/data,volume-nocopy',
              '--mount', f'type=volume,source={volumes[1]},target=/uploads,volume-nocopy']
    base = 'http://127.0.0.1:' + port
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    password = secrets.token_urlsafe(24)

    def get(path, opener=client):
        with opener.open(base + path, timeout=10) as response:
            return response.read().decode(), response.geturl()

    def post(path, values):
        page, _ = get(path)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        data = urllib.parse.urlencode(dict(values, csrf_token=token)).encode()
        with client.open(base + path, data=data, timeout=15) as response:
            return response.read().decode(), response.geturl()

    def query(sql):
        script = 'import sqlite3,json,sys; c=sqlite3.connect("file:/data/timber.db?mode=ro",uri=True); print(json.dumps(c.execute(sys.argv[1]).fetchall()))'
        return json.loads(docker('exec', name, 'python', '-c', script, sql))

    def start():
        docker('run', '-d', '--platform', 'linux/amd64', '--name', name, '--user', '99:100', '-p', port + ':2112', *mounts, image)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if json.loads(get('/health')[0]) == {'status': 'ok'}:
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.5)
        raise AssertionError('Container did not become healthy')

    def remove():
        docker('stop', '--time', '40', name)
        assert docker('inspect', '--format', '{{.State.ExitCode}}', name) == '0'
        docker('rm', name)

    def quote_post(qid, action, **values):
        revision = query(f'SELECT revision FROM quote WHERE id={qid}')[0][0]
        return post(f'/quotes/{qid}', dict(action=action, revision=revision, **values))

    try:
        for volume in volumes:
            docker('volume', 'create', volume)
        # Equivalent to preparing Unraid appdata ownership; no application data yet.
        docker('run', '--rm', '--platform', 'linux/amd64', '--user', '0', *mounts, '--entrypoint', 'python', image,
               '-c', 'import os; [os.chown(p,99,100) for p in ("/data","/uploads")]')
        start()
        assert get('/')[1].endswith('/setup')
        _, url = post('/setup', {'email': 'deployment@example.test', 'password': password, 'confirm_password': password})
        assert url == base + '/'
        assert query('SELECT count(*) FROM user')[0][0] == 1
        assert query('SELECT password_hash FROM user')[0][0] != password
        _, url = post('/customers', {'name': 'Deployment customer', 'email': 'customer@example.test'})
        cid = int(url.rsplit('/', 1)[1])
        _, url = post('/quotes/new', {'customer_id': cid, 'title': 'Persistent deployment quote'})
        qid = int(url.rsplit('/', 1)[1])
        quote_post(qid, 'add_room', name='Living room')
        rid = query('SELECT id FROM room')[0][0]
        quote_post(qid, 'add_item', room_id=rid, name='Full wall', type='PANELLING_FULL')
        iid = query('SELECT id FROM work_item')[0][0]
        quote_post(qid, 'edit_item', room_id=rid, item_id=iid, name='Full wall', type='PANELLING_FULL',
                   subtype='plain', mdf_id='mdf-9mm', ledge_width=18, position=0, wall_length=3000,
                   height=2400, horizontal_squares=4, vertical_squares=2, slat_width=100)
        assert json.loads(query('SELECT result FROM quote')[0][0])['valid']
        pricing = json.loads(query('SELECT "values" FROM pricing_config')[0][0])
        pricing['delivery_cost'] = pricing['delivery_cost'] + 7
        post('/materials', dict(action='pricing', **pricing))
        post('/materials', dict(material_id='mdf-9mm', length_mm=2440, width_mm=1220,
                               thickness_mm=9, price=27, active='on'))
        assert query("SELECT price FROM material WHERE id='mdf-9mm'")[0][0] == 27
        assert json.loads(query('SELECT "values" FROM pricing_config')[0][0]) == pricing
        tables = ('user', 'customer', 'quote', 'room', 'work_item', 'material', 'pricing_config', 'alembic_version')
        before = {table: query(f'SELECT * FROM "{table}" ORDER BY 1') for table in tables}
        key_hash = docker('exec', name, 'python', '-c', 'import hashlib; print(hashlib.sha256(open("/data/session.key","rb").read()).hexdigest())')
        docker('exec', name, 'python', '-c', 'from pathlib import Path; Path("/uploads/persistence-probe").write_text("retained")')
        docker('exec', name, 'python', '/app/docker/healthcheck.py')
        remove()
        start()
        assert {table: query(f'SELECT * FROM "{table}" ORDER BY 1') for table in tables} == before
        assert docker('exec', name, 'python', '-c', 'import hashlib; print(hashlib.sha256(open("/data/session.key","rb").read()).hexdigest())') == key_hash
        assert docker('exec', name, 'cat', '/uploads/persistence-probe') == 'retained'
        assert 'Persistent deployment quote' in get(f'/quotes/{qid}')[0]  # original signed cookie survives
        assert get('/setup')[1] == base + '/'
        anonymous = urllib.request.build_opener()
        assert urllib.parse.urlparse(get('/quotes', anonymous)[1]).path == '/login'
        for path in ('/data/timber.db', '/uploads/persistence-probe'):
            try:
                get(path)
                raise AssertionError('Persistent files were publicly served')
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
        # Normal login is still available after recreation, independently of cookie persistence.
        page, _ = get('/')
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        with client.open(base + '/logout', data=urllib.parse.urlencode({'csrf_token': token}).encode(), timeout=10):
            pass
        assert post('/login', {'email': 'deployment@example.test', 'password': password})[1] == base + '/'
        assert 'Persistent deployment quote' in get('/quotes')[0]
        print('PASS: fresh migrations/admin, CSRF-protected login/quote edits, material/pricing persistence,')
        print('replacement migrations, saved snapshots, session key/cookie, uploads, health, authentication,')
        print('non-root Unraid UID 99:100, private data paths and graceful SIGTERM shutdown.')
        remove()
    except Exception:
        subprocess.run(['docker', 'logs', '--tail', '60', name], check=False)
        raise
    finally:
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for volume in volumes:
            subprocess.run(['docker', 'volume', 'rm', volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
