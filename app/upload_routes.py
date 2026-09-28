"""Private photo and receipt views and upload actions."""
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from .models import db, Quote, Room, WorkItem, WorkItemPhoto, Receipt, Customer
from .calculations.packing import CalculationError
from .services.uploads import TYPES, photo_dir, receipt_dir, remove_upload, save_upload, stored_path

uploads = Blueprint('uploads', __name__)


def quote_item(quote_id, item_id):
    item = db.get_or_404(WorkItem, item_id)
    if item.room.quote_id != quote_id:
        abort(404)
    return item


def private_file(path):
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype=TYPES[path.suffix][0], as_attachment=False)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    return response


def receipt_fields(quote):
    supplier = request.form.get('supplier', '').strip()
    if not supplier or len(supplier) > 200:
        raise CalculationError('Supplier is required (maximum 200 characters).')
    try:
        receipt_date = date.fromisoformat(request.form.get('receipt_date', ''))
    except ValueError:
        raise CalculationError('Enter a valid receipt date.') from None
    try:
        total = Decimal(request.form.get('receipt_total', '')).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        raise CalculationError('Enter a valid receipt total.') from None
    if not total.is_finite() or total < 0 or total > 10000000:
        raise CalculationError('Enter a valid receipt total.')
    room_value = request.form.get('room_id', '').strip()
    room_id = int(room_value) if room_value.isdigit() else None
    if room_value and (room_id is None or not any(room.id == room_id for room in quote.rooms)):
        raise CalculationError('Choose a room from this quote.')
    return dict(supplier=supplier, receipt_date=receipt_date,
                receipt_total=total, room_id=room_id)


@uploads.post('/quotes/<int:quote_id>/items/<int:item_id>/photos')
@login_required
def upload_item_photos(quote_id, item_id):
    item = quote_item(quote_id, item_id)
    files = [file for file in request.files.getlist('photos') if file.filename]
    saved = []
    try:
        if not 1 <= len(files) <= 10:
            raise CalculationError('Choose 1–10 photos per upload.')
        caption = request.form.get('caption', '').strip()
        if len(caption) > 500:
            raise CalculationError('Photo caption must be 500 characters or fewer.')
        for file in files:
            name, original = save_upload(file, photo_dir(quote_id, item_id))
            saved.append(name)
            item.photos.append(WorkItemPhoto(stored_filename=name, original_filename=original, caption=caption))
        db.session.commit()
        flash('Photos uploaded.', 'success')
    except Exception as exc:
        db.session.rollback()
        for name in saved:
            remove_upload(photo_dir(quote_id, item_id), name)
        if not isinstance(exc, CalculationError):
            raise
        flash(str(exc), 'error')
    return redirect(url_for('web.quote_edit', quote_id=quote_id) + f'#item-{item_id}')


@uploads.post('/quotes/<int:quote_id>/items/<int:item_id>/photos/<int:photo_id>/delete')
@login_required
def delete_item_photo(quote_id, item_id, photo_id):
    quote_item(quote_id, item_id)
    photo = db.get_or_404(WorkItemPhoto, photo_id)
    if photo.work_item_id != item_id:
        abort(404)
    name = photo.stored_filename
    db.session.delete(photo)
    db.session.commit()
    remove_upload(photo_dir(quote_id, item_id), name)
    flash('Photo removed.', 'success')
    return redirect(url_for('web.quote_edit', quote_id=quote_id) + f'#item-{item_id}')


@uploads.get('/quotes/<int:quote_id>/items/<int:item_id>/photos/<int:photo_id>')
@login_required
def view_item_photo(quote_id, item_id, photo_id):
    quote_item(quote_id, item_id)
    photo = db.get_or_404(WorkItemPhoto, photo_id)
    if photo.work_item_id != item_id:
        abort(404)
    return private_file(stored_path(photo_dir(quote_id, item_id), photo.stored_filename))


@uploads.post('/quotes/<int:quote_id>/receipts')
@login_required
def upload_receipt(quote_id):
    quote = db.get_or_404(Quote, quote_id)
    name = None
    try:
        fields = receipt_fields(quote)
        file = request.files.get('file')
        if not file or not file.filename:
            raise CalculationError('Choose a receipt image or PDF.')
        name, original = save_upload(file, receipt_dir(quote_id), allow_pdf=True)
        quote.receipts.append(Receipt(**fields,stored_filename=name, original_filename=original))
        db.session.commit()
        flash('Receipt uploaded.', 'success')
    except Exception as exc:
        db.session.rollback()
        if name:
            remove_upload(receipt_dir(quote_id), name)
        if not isinstance(exc, CalculationError):
            raise
        flash(str(exc), 'error')
    return redirect(url_for('web.quote_edit', quote_id=quote_id) + '#receipts')


@uploads.post('/receipts/<int:receipt_id>/edit')
@login_required
def edit_receipt(receipt_id):
    receipt = db.get_or_404(Receipt, receipt_id)
    try:
        for key, value in receipt_fields(receipt.quote).items():
            setattr(receipt, key, value)
        db.session.commit()
        flash('Receipt details saved.', 'success')
    except CalculationError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
    return redirect(url_for('web.quote_edit', quote_id=receipt.quote_id) + '#receipts')


@uploads.get('/receipts/<int:receipt_id>/file')
@login_required
def view_receipt(receipt_id):
    receipt = db.get_or_404(Receipt, receipt_id)
    return private_file(stored_path(receipt_dir(receipt.quote_id), receipt.stored_filename))


@uploads.post('/receipts/<int:receipt_id>/delete')
@login_required
def delete_receipt(receipt_id):
    receipt = db.get_or_404(Receipt, receipt_id)
    quote_id, name = receipt.quote_id, receipt.stored_filename
    db.session.delete(receipt)
    db.session.commit()
    remove_upload(receipt_dir(quote_id), name)
    flash('Receipt removed.', 'success')
    return redirect(url_for('web.quote_edit', quote_id=quote_id) + '#receipts')


@uploads.get('/receipts')
@login_required
def receipts():
    query = db.select(Receipt).join(Quote).join(Customer).outerjoin(Room, Receipt.room_id == Room.id)
    filters = {key: request.args.get(key, '').strip()[:200] for key in ('job', 'customer', 'room', 'supplier')}
    if filters['job']:
        term = filters['job'].removeprefix('TT-')
        clauses = [Quote.title.ilike('%' + filters['job'] + '%')]
        if term.isdigit():
            clauses.append(Quote.id == int(term))
        query = query.where(db.or_(*clauses))
    if filters['customer']:
        query = query.where(Customer.name.ilike('%' + filters['customer'] + '%'))
    if filters['room']:
        query = query.where(Room.name.ilike('%' + filters['room'] + '%'))
    if filters['supplier']:
        query = query.where(Receipt.supplier.ilike('%' + filters['supplier'] + '%'))
    rows = db.session.scalars(query.order_by(Receipt.receipt_date.desc(), Receipt.id.desc())).all()
    return render_template('receipts.html', receipts=rows, filters=filters)
