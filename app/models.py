from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

def now(): return datetime.now(timezone.utc).replace(tzinfo=None)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(512), nullable=False)
    is_admin = db.Column(db.Boolean, default=True, nullable=False)
    failed_logins = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), default='')
    telephone = db.Column(db.String(80), default='')
    address = db.Column(db.Text, default='')
    postcode = db.Column(db.String(30), default='')
    notes = db.Column(db.Text, default='')
    quotes = db.relationship('Quote', back_populates='customer')

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    title = db.Column(db.String(200), default='Panelling quotation', nullable=False)
    status = db.Column(db.String(30), default='Draft', nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    updated_at = db.Column(db.DateTime, default=now, nullable=False)
    measure_at = db.Column(db.DateTime)
    quote_date = db.Column(db.Date)
    accepted_date = db.Column(db.Date)
    planned_job_date = db.Column(db.Date)
    full_days = db.Column(db.Float, default=0, nullable=False)
    extra_hours = db.Column(db.Float, default=0, nullable=False)
    notes = db.Column(db.Text, default='')
    snapshot = db.Column(db.JSON, nullable=False)
    result = db.Column(db.JSON, default=dict, nullable=False)
    revision = db.Column(db.Integer, default=1, nullable=False)
    __mapper_args__ = {'version_id_col': revision}
    customer = db.relationship('Customer', back_populates='quotes')
    rooms = db.relationship('Room', back_populates='quote', cascade='all, delete-orphan', order_by='Room.position, Room.id')
    consumables = db.relationship('QuoteConsumable', back_populates='quote', cascade='all, delete-orphan')
    additional_charges = db.relationship('AdditionalCharge', back_populates='quote', cascade='all, delete-orphan')
    payments = db.relationship('Payment', back_populates='quote', cascade='all, delete-orphan', order_by='Payment.paid_at, Payment.id')
    material_states = db.relationship('JobMaterialState', back_populates='quote', cascade='all, delete-orphan')
    purchases = db.relationship('JobPurchase', back_populates='quote', cascade='all, delete-orphan')
    receipts = db.relationship('Receipt', back_populates='quote', cascade='all, delete-orphan', order_by='Receipt.id.desc()')
    @property
    def reference(self): return f'TT-{self.id:06d}'

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    notes = db.Column(db.Text, default='')
    quote = db.relationship('Quote', back_populates='rooms')
    items = db.relationship('WorkItem', back_populates='room', cascade='all, delete-orphan', order_by='WorkItem.position, WorkItem.id')

class WorkItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(60), nullable=False)
    subtype = db.Column(db.String(60), default='plain', nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)
    notes = db.Column(db.Text, default='')
    inputs = db.Column(db.JSON, default=dict, nullable=False)
    options = db.Column(db.JSON, default=dict, nullable=False)
    result = db.Column(db.JSON, default=dict, nullable=False)
    pricing_result = db.Column(db.JSON, default=dict, nullable=False)
    room = db.relationship('Room', back_populates='items')
    photos = db.relationship('WorkItemPhoto', back_populates='work_item', cascade='all, delete-orphan', order_by='WorkItemPhoto.id')


class WorkItemPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    work_item_id = db.Column(db.Integer, db.ForeignKey('work_item.id'), nullable=False)
    stored_filename = db.Column(db.String(100), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=now, nullable=False)
    caption = db.Column(db.String(500), nullable=False, default='')
    work_item = db.relationship('WorkItem', back_populates='photos')


class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    supplier = db.Column(db.String(200), nullable=False)
    receipt_date = db.Column(db.Date, nullable=False)
    receipt_total = db.Column(db.Numeric(12, 2), nullable=False)
    stored_filename = db.Column(db.String(100), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=now, nullable=False)
    quote = db.relationship('Quote', back_populates='receipts')
    room = db.relationship('Room')

class Material(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    category = db.Column(db.String(30), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    profile = db.Column(db.String(100), default='')
    length_mm = db.Column(db.Float, nullable=False)
    width_mm = db.Column(db.Float, nullable=False)
    thickness_mm = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    preferred_stock_mm = db.Column(db.Float)
    uses = db.Column(db.JSON, nullable=False, default=list)
    def as_dict(self):
        return {c.name:getattr(self,c.name) for c in self.__table__.columns}

class PricingConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    values = db.Column(db.JSON, nullable=False)


class Consumable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(200), nullable=False)
    unit_label = db.Column(db.String(80), nullable=False, default='unit')
    price = db.Column(db.Float, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)


class QuoteConsumable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    consumable_id = db.Column(db.Integer, db.ForeignKey('consumable.id'))
    label = db.Column(db.String(200), nullable=False)
    unit_label = db.Column(db.String(80), nullable=False, default='unit')
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False, default=0)
    quote = db.relationship('Quote', back_populates='consumables')
    consumable = db.relationship('Consumable')


class AdditionalCharge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    quote = db.relationship('Quote', back_populates='additional_charges')


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_at = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(30), nullable=False, default='Other')
    note = db.Column(db.String(500), nullable=False, default='')
    quote = db.relationship('Quote', back_populates='payments')


class JobMaterialState(db.Model):
    """Room-specific additions to calculated material demand.

    A null room_id is retained for legacy quote-level additions whose room
    cannot be inferred safely.
    """
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    material_id = db.Column(db.String(100), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    extra_quantity = db.Column(db.Integer, nullable=False, default=0)
    dimensional_extras = db.Column(db.JSON, nullable=True)
    quote = db.relationship('Quote', back_populates='material_states')
    room = db.relationship('Room')
    __table_args__ = (db.UniqueConstraint('quote_id', 'material_id', 'room_id', name='uq_job_material_state_room'),)


class JobPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    material_id = db.Column(db.String(100), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    stock_length_mm = db.Column(db.Float)
    stock_width_mm = db.Column(db.Float)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    purchased_at = db.Column(db.Date, nullable=False)
    quote = db.relationship('Quote', back_populates='purchases')


class OwnedStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.String(100), nullable=False)
    stock_type = db.Column(db.String(20), nullable=False, default='offcut')
    usable_length_mm = db.Column(db.Float)
    usable_width_mm = db.Column(db.Float)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    reserved_quantity = db.Column(db.Integer, nullable=False, default=0)
    consumed_quantity = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.String(500), nullable=False, default='')
    source_quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'))
    active = db.Column(db.Boolean, nullable=False, default=True)
    allocations = db.relationship('OwnedStockAllocation', back_populates='owned_stock', cascade='all, delete-orphan')


class OwnedStockAllocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owned_stock_id = db.Column(db.Integer, db.ForeignKey('owned_stock.id'), nullable=False)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    material_id = db.Column(db.String(100), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    stock_length_mm = db.Column(db.Float)
    stock_width_mm = db.Column(db.Float)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    consumed = db.Column(db.Boolean, nullable=False, default=False)
    owned_stock = db.relationship('OwnedStock', back_populates='allocations')
    quote = db.relationship('Quote')
