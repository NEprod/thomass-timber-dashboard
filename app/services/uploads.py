"""Validated, private files on the existing persistent /uploads mount."""
import os
import re
import uuid
from pathlib import Path
from flask import current_app
from ..calculations.packing import CalculationError

MAX_FILE_BYTES = 25 * 1024 * 1024
TYPES = {
    '.jpg': ('image/jpeg', lambda b: b.startswith(b'\xff\xd8\xff')),
    '.jpeg': ('image/jpeg', lambda b: b.startswith(b'\xff\xd8\xff')),
    '.png': ('image/png', lambda b: b.startswith(b'\x89PNG\r\n\x1a\n')),
    '.pdf': ('application/pdf', lambda b: b.startswith(b'%PDF-')),
}
STORED_NAME = re.compile(r'^[0-9a-f]{32}\.(?:jpg|jpeg|png|pdf)$')


def upload_root():
    return Path(current_app.config['UPLOAD_DIR'])


def photo_dir(quote_id, item_id):
    return upload_root() / 'job-images' / str(int(quote_id)) / str(int(item_id))


def receipt_dir(quote_id):
    return upload_root() / 'receipts' / str(int(quote_id))


def stored_path(folder, name):
    if not STORED_NAME.fullmatch(name or ''):
        raise CalculationError('Invalid stored file name.')
    return folder / name


def save_upload(file, folder, *, allow_pdf=False):
    original = (file.filename or '').replace('\\', '/').rsplit('/', 1)[-1][:255]
    suffix = Path(original).suffix.lower()
    if suffix not in TYPES or (suffix == '.pdf' and not allow_pdf):
        raise CalculationError('Choose a JPG or PNG image' + (' or PDF receipt.' if allow_pdf else '.'))
    expected_mime, valid_magic = TYPES[suffix]
    if file.mimetype != expected_mime:
        raise CalculationError('File type does not match its name.')
    first = file.stream.read(16)
    if not valid_magic(first):
        raise CalculationError('File contents do not match the selected type.')
    folder.mkdir(parents=True, exist_ok=True)
    directory = folder
    while directory != upload_root():
        os.chmod(directory, 0o755)
        directory = directory.parent
    name = uuid.uuid4().hex + suffix
    path = stored_path(folder, name)
    size = 0
    try:
        with path.open('xb') as output:
            output.write(first)
            size += len(first)
            while chunk := file.stream.read(1024 * 1024):
                size += len(chunk)
                if size > current_app.config.get('MAX_UPLOAD_FILE_BYTES', MAX_FILE_BYTES):
                    raise CalculationError('Each upload must be 25 MB or smaller.')
                output.write(chunk)
        if not size:
            raise CalculationError('Choose a non-empty file.')
        os.chmod(path, 0o644)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return name, original


def remove_upload(folder, name):
    stored_path(folder, name).unlink(missing_ok=True)
