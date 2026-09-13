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
