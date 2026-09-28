from io import BytesIO
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app import configure_file_logging
from app.calculations.pricing import aggregate
from app.calculations.sections import calculate
from app.models import db, Quote, WorkItem, WorkItemPhoto, Receipt, PricingConfig, JobPurchase
from app.services.quotes import material_plan
from app.services.uploads import photo_dir, receipt_dir
from test_application import create_quote, add_room, post_quote


PNG = b'\x89PNG\r\n\x1a\n' + b'job-site-image'
JPEG = b'\xff\xd8\xff\xe0' + b'job-site-image'
PDF = b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF'


def current_quote(app, client):
    quote_id = create_quote(client, app)
    room_id = add_room(client, app, quote_id, 'Living Room')
    assert post_quote(client, app, quote_id, 'add_item', room_id=room_id,
                      name='Coving wall', type='COVING').status_code == 302
    with app.app_context():
        item_id = db.session.scalar(db.select(WorkItem.id).where(WorkItem.room_id == room_id))
    assert post_quote(client, app, quote_id, 'edit_item', room_id=room_id,
                      item_id=item_id, name='Coving wall', type='COVING', subtype='plain',
                      wall_length=2000, start_corner='Internal', end_corner='Internal', position=0).status_code == 302
    return quote_id, room_id, item_id


def test_multiple_work_item_photos_private_reopen_and_delete(app, signed_in, tmp_path):
    app.config['UPLOAD_DIR'] = str(tmp_path / 'uploads')
    qid, rid, iid = current_quote(app, signed_in)
    upload = f'/quotes/{qid}/items/{iid}/photos'
    response = signed_in.post(upload, data={'caption': 'Before work', 'photos': [
        (BytesIO(PNG), 'first.png', 'image/png'),
        (BytesIO(JPEG), 'second.jpg', 'image/jpeg')]}, content_type='multipart/form-data')
    assert response.status_code == 302
    with app.app_context():
        photos = db.session.scalars(db.select(WorkItemPhoto).order_by(WorkItemPhoto.id)).all()
        assert len(photos) == 2 and all(photo.work_item_id == iid for photo in photos)
        first, second = photos[0].id, photos[1].id
        first_file = tmp_path / 'uploads' / 'job-images' / str(qid) / str(iid) / photos[0].stored_filename
        second_file = tmp_path / 'uploads' / 'job-images' / str(qid) / str(iid) / photos[1].stored_filename
        assert first_file.is_file() and second_file.is_file()
        assert first_file.stat().st_mode & 0o777 == 0o644
        assert first_file.parent.stat().st_mode & 0o777 == 0o755
    assert b'Before work' in signed_in.get(f'/quotes/{qid}').data
    assert signed_in.get(f'/quotes/{qid}/items/{iid}/photos/{first}').data == PNG
    assert signed_in.get(f'/uploads/job-images/{qid}/{iid}/{first_file.name}').status_code == 404
    assert signed_in.post(f'/quotes/{qid}/items/{iid}/photos/{first}/delete').status_code == 302
    with app.app_context():
        assert db.session.get(WorkItemPhoto, first) is None
        assert db.session.get(WorkItemPhoto, second) is not None
    assert not first_file.exists() and second_file.exists()
    assert signed_in.post(upload, data={'photos': (BytesIO(b'evil'), '../outside.py', 'text/x-python')},
                          content_type='multipart/form-data').status_code == 302
    assert not (tmp_path / 'outside.py').exists()
    assert signed_in.post(upload, data={'photos': (BytesIO(PNG), '../traversal.png', 'image/png')},
                          content_type='multipart/form-data').status_code == 302
    assert not (tmp_path / 'traversal.png').exists()
    app.config['MAX_UPLOAD_FILE_BYTES'] = 8
    assert signed_in.post(upload, data={'photos': (BytesIO(PNG), 'too-big.png', 'image/png')},
                          content_type='multipart/form-data').status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(WorkItemPhoto)) == 2
    assert post_quote(signed_in, app, qid, 'delete_item', room_id=rid, item_id=iid).status_code == 302
    assert not second_file.exists()
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(WorkItemPhoto)) == 0


def test_receipts_register_files_metadata_and_deletion(app, signed_in, tmp_path):
    app.config['UPLOAD_DIR'] = str(tmp_path / 'uploads')
    qid, rid, _ = current_quote(app, signed_in)
    endpoint = f'/quotes/{qid}/receipts'
    for name, blob, mime, room in [('shop.png', PNG, 'image/png', str(rid)),
                                   ('invoice.pdf', PDF, 'application/pdf', '')]:
        response = signed_in.post(endpoint, data={'supplier': 'Timber Shop', 'receipt_date': '2026-09-28',
            'receipt_total': '12.34', 'room_id': room, 'file': (BytesIO(blob), name, mime)},
            content_type='multipart/form-data')
        assert response.status_code == 302
    with app.app_context():
        receipts = db.session.scalars(db.select(Receipt).order_by(Receipt.id)).all()
        assert len(receipts) == 2
        assert receipts[0].room_id == rid and receipts[1].room_id is None
        assert str(receipts[0].receipt_total) == '12.34'
        first, second = receipts[0].id, receipts[1].id
        path = tmp_path / 'uploads' / 'receipts' / str(qid) / receipts[0].stored_filename
        assert path.is_file() and path.stat().st_mode & 0o777 == 0o644
    page = signed_in.get('/receipts?job=TT-000001&customer=Test&room=Living&supplier=Timber').data
    assert b'Timber Shop' in page and b'Living Room' in page and b'shop.png' in page
    assert signed_in.get(f'/receipts/{first}/file').data == PNG
    assert signed_in.get(f'/receipts/{second}/file').data == PDF
    assert signed_in.post(f'/receipts/{second}/edit', data={'supplier': 'Revised Shop',
        'receipt_date': '2026-09-29', 'receipt_total': '15.67', 'room_id': str(rid)}).status_code == 302
    with app.app_context():
        revised = db.session.get(Receipt, second)
        assert revised.supplier == 'Revised Shop' and revised.room_id == rid
        assert str(revised.receipt_total) == '15.67'
        assert revised.original_filename == 'invoice.pdf'
    assert signed_in.post(f'/receipts/{first}/delete').status_code == 302
    with app.app_context():
        assert db.session.get(Receipt, first) is None
        assert db.session.get(Receipt, second) is not None
    assert not path.exists()


def test_mastic_coving_beads_stock_and_purchase(app, signed_in, catalogue):
    internal = calculate('COVING', 'plain', {'wall_length': 2000, 'start_corner': 'Internal',
        'end_corner': 'Internal'}, {}, catalogue, 3, 'wall', 10)
    external = calculate('COVING', 'plain', {'wall_length': 2000, 'start_corner': 'External',
        'end_corner': 'External'}, {}, catalogue, 3, 'wall', 10)
    with app.app_context():
        config = db.session.get(PricingConfig, 1)
        values = dict(config.values, mastic_linear_coverage=1, mastic_on_hand=4)
        config.values = values
        db.session.commit()
    assert aggregate([internal], catalogue, values)['mastic_units'] == 6
    assert aggregate([external], catalogue, values)['mastic_units'] == 6
    qid, _, _ = current_quote(app, signed_in)
    with app.app_context():
        q = db.session.get(Quote, qid)
        row = next(row for row in material_plan(q) if row.get('is_calculated_consumable'))
        before = (q.result['chargeable_material_cost'], q.result['final_price'], q.result['mastic_cost'])
        assert row['calculated_quantity'] == 6 and row['allocated_owned_quantity'] == 4
        assert row['need_to_purchase_quantity'] == 2 and row['chargeable_cost'] == 6 * values['mastic_unit_price']
        q.status = 'Accepted'
        db.session.commit()
    assert b'Mastic' in signed_in.get('/').data
    assert post_quote(signed_in, app, qid, 'mark_material_purchased',
                      material_id='calculated-mastic', quantity=2).status_code == 302
    with app.app_context():
        q = db.session.get(Quote, qid)
        row = next(row for row in material_plan(q) if row.get('is_calculated_consumable'))
        assert row['need_to_purchase_quantity'] == 0 and row['purchased_quantity'] == 2
        assert (q.result['chargeable_material_cost'], q.result['final_price'], q.result['mastic_cost']) == before
        assert len([p for p in q.purchases if p.material_id == 'calculated-mastic']) == 1
        config = db.session.get(PricingConfig, 1)
        config.values = dict(config.values, mastic_on_hand=10)
        db.session.commit()
        assert next(row for row in material_plan(q) if row.get('is_calculated_consumable'))['need_to_purchase_quantity'] == 0
    assert b'<td>Mastic</td>' not in signed_in.get('/').data
    second_quote, _, _ = current_quote(app, signed_in)
    with app.app_context():
        q = db.session.get(Quote, second_quote)
        row = next(row for row in material_plan(q) if row.get('is_calculated_consumable'))
        assert row['need_to_purchase_quantity'] == 0
        assert row['chargeable_cost'] == q.result['mastic_cost'] > 0


def test_persistent_roots_and_rotating_handler(app, tmp_path):
    app.config['DATA_DIR'] = str(tmp_path / 'data')
    app.config['UPLOAD_DIR'] = str(tmp_path / 'uploads')
    with app.app_context():
        assert photo_dir(1, 2).is_relative_to(Path(app.config['UPLOAD_DIR']))
        assert receipt_dir(1).is_relative_to(Path(app.config['UPLOAD_DIR']))
        configure_file_logging(app)
        handlers = [h for h in app.logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(handlers) == 1
        handler = handlers[0]
        assert handler.baseFilename == str(tmp_path / 'data' / 'logs' / 'app.log')
        assert handler.maxBytes == 10 * 1024 * 1024 and handler.backupCount == 5
        assert Path(handler.baseFilename).stat().st_mode & 0o777 == 0o644
        app.logger.removeHandler(handler)
        handler.close()
