from datetime import datetime, date, timedelta
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text
from sqlalchemy.orm.exc import StaleDataError
from .models import db, User, Customer, Quote, Room, WorkItem, Material, PricingConfig, now
from .calculations.sections import TYPES, SUBTYPES, DADO_STYLES
from .calculations.dado import USES, rail_choices, SUPPORTED_DADO_STYLES, dado_summary
from .calculations.packing import number, CalculationError
from .services.quotes import current_snapshot, recalculate_item, reaggregate, refresh_prices

web=Blueprint('web',__name__)
STATUSES=['Draft','Measure Booked','Measured','Quoted','Sent','Accepted','Declined','Cancelled']

def field(key, required=False, limit=200, source=None):
    value=(source or request.form).get(key,'').strip()
    if len(value)>limit or (required and not value):raise CalculationError(f'{key.replace("_"," ").capitalize()} is required (maximum {limit} characters).')
    return value

def email_value():
    value=field('email',limit=254).lower()
    if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise CalculationError('Enter a valid email address.')
    return value

def password_value():
    password=request.form.get('password','')
    if len(password)<12 or len(password)>256:raise CalculationError('Use a password of 12–256 characters.')
    if password!=request.form.get('confirm_password'):raise CalculationError('Passwords do not match.')
    return password

def date_value(name, with_time=False):
    value=request.form.get(name,'').strip()
    if not value:return None
    try:return datetime.fromisoformat(value) if with_time else date.fromisoformat(value)
    except ValueError:raise CalculationError(f'Enter a valid {name.replace("_"," ")}.') from None

@web.before_app_request
def first_run_guard():
    if request.endpoint in ('static','web.health'):return
    if not inspect(db.engine).has_table('user'):
        return render_template('uninitialized.html'),503
    if not db.session.scalar(db.select(User.id).limit(1)) and request.endpoint!='web.setup':
        return redirect(url_for('web.setup'))

@web.get('/health')
def health():
    return {'status':'ok'}

@web.app_context_processor
def shared():return dict(types=TYPES,subtypes=SUBTYPES,dado_styles=DADO_STYLES,supported_dado_styles=SUPPORTED_DADO_STYLES,dado_summary=dado_summary,dado_uses=USES,dado_rail_choices=rail_choices,statuses=STATUSES)

@web.route('/setup',methods=['GET','POST'])
def setup():
    if db.session.scalar(db.select(User.id).limit(1)):
        return redirect(url_for('web.login_view'))
    if request.method=='POST':
        try:
            email=email_value()
            if not email:raise CalculationError('Email is required.')
            password=password_value()
            db.session.rollback()
            db.session.execute(text('BEGIN IMMEDIATE'))
            if db.session.scalar(db.select(User.id).limit(1)):
                db.session.rollback();return redirect(url_for('web.login_view'))
            user=User(email=email,password_hash=generate_password_hash(password))
            db.session.add(user);db.session.commit()
            session.clear();login_user(user);session.permanent=True
            flash('Your workspace is ready. Start with a customer and a quotation.','success')
            return redirect(url_for('web.dashboard'))
        except CalculationError as exc:
            db.session.rollback();flash(str(exc),'error')
    return render_template('auth.html',setup=True)

@web.route('/login',methods=['GET','POST'])
def login_view():
    if current_user.is_authenticated:return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        email=request.form.get('email','').strip().lower()
        user=db.session.scalar(db.select(User).where(User.email==email))
        password=request.form.get('password','')[:256]
        if user and (not user.locked_until or user.locked_until<=now()) and check_password_hash(user.password_hash,password):
            user.failed_logins=0;user.locked_until=None;db.session.commit()
            session.clear();login_user(user);session.permanent=True
            return redirect(url_for('web.dashboard'))
        if user:
            user.failed_logins+=1
            if user.failed_logins>=5:user.locked_until=now()+timedelta(minutes=5)
            db.session.commit()
        flash('Unable to sign in. Check your credentials or retry in five minutes.','error')
    return render_template('auth.html',setup=False)

@web.post('/logout')
@login_required
def logout():
    logout_user();session.clear();return redirect(url_for('web.login_view'))

@web.get('/')
@login_required
def dashboard():
    quotes=db.session.scalars(db.select(Quote).order_by(Quote.updated_at.desc())).all()
    today=date.today()
    measures=sorted([q for q in quotes if q.measure_at and q.measure_at.date()>=today and q.status not in ('Declined','Cancelled')],key=lambda q:q.measure_at)[:4]
    jobs=sorted([q for q in quotes if q.planned_job_date and q.planned_job_date>=today and q.status=='Accepted'],key=lambda q:q.planned_job_date)[:4]
    return render_template('dashboard.html',quotes=quotes[:6],counts={s:sum(q.status==s for q in quotes) for s in STATUSES},measures=measures,jobs=jobs)

@web.get('/quotes')
@login_required
def quotes():
    status=request.args.get('status','');search=request.args.get('q','').strip()
    query=db.select(Quote).join(Customer)
    if status in STATUSES:query=query.where(Quote.status==status)
    if search:query=query.where(db.or_(Customer.name.ilike('%'+search+'%'),Quote.title.ilike('%'+search+'%')))
    return render_template('quotes.html',quotes=db.session.scalars(query.order_by(Quote.updated_at.desc())).all(),selected_status=status,search=search)

@web.route('/customers',methods=['GET','POST'])
@login_required
def customers():
    if request.method=='POST':
        try:
            c=Customer();update_customer(c);db.session.add(c);db.session.commit()
            flash('Customer created.','success');return redirect(url_for('web.customer_edit',customer_id=c.id))
        except CalculationError as exc:db.session.rollback();flash(str(exc),'error')
    return render_template('customers.html',customers=db.session.scalars(db.select(Customer).order_by(Customer.name)).all())

def update_customer(c):
    values=dict(name=field('name',True),email=email_value(),telephone=field('telephone',limit=80),address=field('address',limit=2000),postcode=field('postcode',limit=30),notes=field('notes',limit=5000))
    for k,v in values.items():setattr(c,k,v)

@web.route('/customers/<int:customer_id>',methods=['GET','POST'])
@login_required
def customer_edit(customer_id):
    c=db.get_or_404(Customer,customer_id)
    if request.method=='POST':
        try:update_customer(c);db.session.commit();flash('Customer saved.','success');return redirect(request.path)
        except CalculationError as exc:db.session.rollback();flash(str(exc),'error')
    return render_template('customer_edit.html',customer=c)

@web.route('/quotes/new',methods=['GET','POST'])
@login_required
def quote_new():
    if request.method=='POST':
        try:
            c=db.session.get(Customer,request.form.get('customer_id',type=int))
            if not c:raise CalculationError('Choose a customer first.')
            q=Quote(customer=c,title=field('title',True),snapshot=current_snapshot(),full_days=0,extra_hours=0)
            db.session.add(q);db.session.flush();reaggregate(q);db.session.commit()
            return redirect(url_for('web.quote_edit',quote_id=q.id))
        except CalculationError as exc:db.session.rollback();flash(str(exc),'error')
    return render_template('quote_new.html',customers=db.session.scalars(db.select(Customer).order_by(Customer.name)).all())

@web.route('/quotes/<int:quote_id>',methods=['GET','POST'])
@login_required
def quote_edit(quote_id):
    q=db.get_or_404(Quote,quote_id)
    if request.method=='POST':
        if request.form.get('revision',type=int)!=q.revision:abort(409,description='This quote changed in another tab. Reload before editing.')
        try:
            action=request.form.get('action')
            if action=='details':
                customer=db.session.get(Customer,request.form.get('customer_id',type=int))
                if not customer:raise CalculationError('Select a customer.')
                status=field('status')
                if status not in STATUSES:raise CalculationError('Choose a valid status.')
                vals=dict(title=field('title',True),status=status,notes=field('notes',limit=5000),
                          full_days=number(request.form.get('full_days'),'Full days',allow_zero=True,maximum=365),
                          extra_hours=number(request.form.get('extra_hours'),'Extra hours',allow_zero=True,maximum=10000),
                          measure_at=date_value('measure_at',True),quote_date=date_value('quote_date'),accepted_date=date_value('accepted_date'),planned_job_date=date_value('planned_job_date'))
                q.customer=customer
                for k,v in vals.items():setattr(q,k,v)
            elif action=='add_room':
                if len(q.rooms)>=50:raise CalculationError('Maximum 50 rooms per quote.')
                q.rooms.append(Room(name=field('name',True),position=len(q.rooms)))
            elif action=='refresh_prices':refresh_prices(q)
            elif action in ('edit_room','delete_room','add_item','edit_item','delete_item'):
                room=next((r for r in q.rooms if r.id==request.form.get('room_id',type=int)),None)
                if not room:abort(404)
                if action=='delete_room':q.rooms.remove(room)
                elif action=='edit_room':
                    room.name=field('name',True);room.notes=field('notes',limit=5000)
                    room.position=int(number(request.form.get('position',0),'Room order',allow_zero=True,maximum=1000))
                elif action=='add_item':
                    if sum(len(r.items) for r in q.rooms)>=100:raise CalculationError('Maximum 100 work items per quote.')
                    kind=field('type')
                    if kind not in TYPES:raise CalculationError('Choose a supported work type.')
                    item=WorkItem(name=field('name',True),type=kind,subtype='Dado' if kind.startswith('DADO_') else 'plain',inputs={'slat_width':100,'horizontal_squares':4,'vertical_squares':1,'gap_width':100,'bottom_squares':4,'top_squares':4},options={'mdf_id':'mdf-9mm','ledge_width':18},position=len(room.items))
                    room.items.append(item);db.session.flush();recalculate_item(item,q.snapshot)
                else:
                    item=next((i for i in room.items if i.id==request.form.get('item_id',type=int)),None)
                    if not item:abort(404)
                    if action=='delete_item':room.items.remove(item)
                    else:
                        if field('type').startswith('DADO_') and field('subtype') not in SUPPORTED_DADO_STYLES:
                            raise CalculationError('This dado style is coming later. The saved item and its results have been kept unchanged; choose an available style explicitly to replace it.')
                        item.name=field('name',True);item.type=field('type');item.subtype=field('subtype')
                        item.notes=field('notes',limit=5000)
                        item.position=int(number(request.form.get('position',0),'Item order',allow_zero=True,maximum=1000))
                        item.inputs={k:field(k,limit=50) for k in ['wall_length','height','horizontal_squares','vertical_squares','slat_width','lower_landing','upper_landing','slope_length','gap_width','bottom_squares','top_squares','bottom_zone_height','top_zone_height','inner_inset']}
                        item.options={k:field(k) for k in ['mdf_id','bead_id','ledge_width','ledge_choice','dado_rail_id','dado_square_id']}
                        item.options['dado_enabled']='dado_enabled' in request.form
                        recalculate_item(item,q.snapshot)
            else:abort(400,description='Unknown quote action.')
            reaggregate(q);db.session.commit();flash('Quote saved. Calculations and totals updated.','success')
            anchor=f"#item-{item.id}" if action in ('edit_item','add_item') else ''
            return redirect(request.path+anchor)
        except CalculationError as exc:db.session.rollback();flash(str(exc),'error')
        except StaleDataError:db.session.rollback();abort(409,description='This quote changed in another session. Reload before editing.')
    return render_template('quote_edit.html',quote=q,customers=db.session.scalars(db.select(Customer).order_by(Customer.name)).all(),catalogue=q.snapshot['catalogue'])

@web.route('/materials',methods=['GET','POST'])
@login_required
def materials():
    if request.method=='POST':
        try:
            if request.form.get('action')=='pricing':
                config=db.session.get(PricingConfig,1)
                vals={k:number(request.form.get(k),k.replace('_',' '),allow_zero=k!='mastic_linear_coverage',maximum=50 if k=='kerf' else 100000) for k in config.values}
                config.values=vals
            else:
                material=db.get_or_404(Material,field('material_id'))
                vals={k:number(request.form.get(k),k.replace('_',' '),allow_zero=k=='price') for k in ['length_mm','width_mm','thickness_mm','price']}
                for k,v in vals.items():setattr(material,k,v)
                if request.form.get('edit_compatibility')=='1':
                    material.label=field('label',True)
                    material.profile=field('profile',True)
                    uses=request.form.getlist('uses')
                    if any(use not in USES for use in uses):raise CalculationError('Unknown material use.')
                    material.uses=list(dict.fromkeys(uses)) if material.category=='dado' else []
                material.active='active' in request.form
            db.session.commit();flash('Current catalogue updated. Existing quote snapshots are unchanged.','success');return redirect(request.path)
        except CalculationError as exc:db.session.rollback();flash(str(exc),'error')
    return render_template('materials.html',materials=db.session.scalars(db.select(Material).order_by(Material.category,Material.label)).all(),pricing=db.session.get(PricingConfig,1).values)

@web.route('/settings',methods=['GET','POST'])
@login_required
def settings():
    if request.method=='POST':
        try:
            if not check_password_hash(current_user.password_hash,request.form.get('current_password','')):raise CalculationError('Current password is incorrect.')
            current_user.password_hash=generate_password_hash(password_value());db.session.commit();flash('Password updated.','success');return redirect(request.path)
        except CalculationError as exc:db.session.rollback();flash(str(exc),'error')
    return render_template('settings.html')
