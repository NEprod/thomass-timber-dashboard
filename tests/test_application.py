from copy import deepcopy
import re
from flask_migrate import upgrade
from app import create_app
from app.models import db, User, Customer, Quote, Room, WorkItem, Material, PricingConfig
from app.seed import seed
from test_calculations import FULL, HALF, STAIR


def create_quote(client,app):
    assert client.post('/customers',data={'name':'Test Customer','email':'customer@example.test','telephone':'01234','address':'1 Timber Lane','postcode':'TT1 1TT','notes':'Measure first'}).status_code==302
    with app.app_context():customer=db.session.scalar(db.select(Customer));customer_id=customer.id
    response=client.post('/quotes/new',data={'customer_id':customer_id,'title':'House panelling'})
    assert response.status_code==302
    return int(response.location.rsplit('/',1)[1])

def post_quote(client,app,quote_id,action,**values):
    with app.app_context():revision=db.session.get(Quote,quote_id).revision
    return client.post(f'/quotes/{quote_id}',data=dict(revision=revision,action=action,**values))

def add_room(client,app,qid,name):
    assert post_quote(client,app,qid,'add_room',name=name).status_code==302
    with app.app_context():return db.session.scalar(db.select(Room).where(Room.quote_id==qid,Room.name==name)).id

def add_item(client,app,qid,rid,name,kind,inputs):
    assert post_quote(client,app,qid,'add_item',room_id=rid,name=name,type=kind).status_code==302
    with app.app_context():iid=db.session.scalar(db.select(WorkItem).where(WorkItem.room_id==rid,WorkItem.name==name)).id
    response=post_quote(client,app,qid,'edit_item',room_id=rid,item_id=iid,name=name,type=kind,subtype='plain',mdf_id='mdf-9mm',ledge_width=18,position=0,**inputs)
    assert response.status_code==302
    return iid

def test_auth_setup_logout_login_and_csrf(app,client):
    assert client.get('/quotes').location.endswith('/setup')
    assert client.get('/setup').status_code==200
    assert client.post('/setup',data={'email':'bad','password':'short'}).status_code==200
    credentials={'email':'admin@example.test','password':'a-secure-test-password','confirm_password':'a-secure-test-password'}
    assert client.post('/setup',data=credentials).status_code==302
    with app.app_context():
        user=db.session.scalar(db.select(User));assert user.password_hash!=credentials['password'];assert user.is_admin
    assert client.post('/setup',data=credentials).status_code==302
    assert client.get('/').status_code==200
    assert client.post('/logout').status_code==302
    assert '/login' in client.get('/customers').location
    assert client.post('/login',data={'email':credentials['email'],'password':'wrong'}).status_code==200
    assert client.post('/login',data=credentials).status_code==302
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/customers',data={'name':'CSRF blocked'}).status_code==400
    page=client.get('/customers').get_data(as_text=True)
    token=re.search(r'name="csrf_token" value="([^"]+)"',page).group(1)
    assert client.post('/customers',data={'name':'CSRF valid','csrf_token':token}).status_code==302


def test_editable_mixed_quote_snapshots_and_invalidation(app,signed_in):
    client=signed_in;qid=create_quote(client,app)
    living=add_room(client,app,qid,'Living room');stairs=add_room(client,app,qid,'Hall & stairs')
    full=add_item(client,app,qid,living,'TV wall','PANELLING_FULL',FULL)
    half=add_item(client,app,qid,living,'Window wall','PANELLING_HALF',HALF)
    stair=add_item(client,app,qid,stairs,'Stair wall','PANELLING_STAIR_HALF',STAIR)
    with app.app_context():
        q=db.session.get(Quote,qid);assert q.reference=='TT-000001';assert q.result['valid']
        before=q.result['final_price'];unchanged=deepcopy(db.session.get(WorkItem,stair).result);snapshot=deepcopy(q.snapshot)
        old_full=deepcopy(db.session.get(WorkItem,full).result)
        unchanged_half=deepcopy(db.session.get(WorkItem,half).result)
        m=db.session.get(Material,'mdf-9mm');m.price+=100;db.session.commit()
    assert client.get(f'/quotes/{qid}').status_code==200
    assert post_quote(client,app,qid,'edit_item',room_id=living,item_id=full,name='TV half wall',type='PANELLING_HALF',subtype='plain',mdf_id='mdf-9mm',ledge_width=18,position=1,**dict(HALF,wall_length=3500)).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid)
        assert q.snapshot==snapshot
        assert db.session.get(WorkItem,stair).result==unchanged
        assert db.session.get(WorkItem,full).type=='PANELLING_HALF'
        assert db.session.get(WorkItem,half).name=='Window wall'
        assert db.session.get(WorkItem,half).result==unchanged_half
        changed=db.session.get(WorkItem,full)
        assert changed.result!=old_full and changed.inputs['wall_length']=='3500'
        assert changed.result['geometry']['square_width']==750
        assert q.result['required_panelling_m']==28.88
        assert q.result['final_price']!=before
        assert q.result['valid']
    assert post_quote(client,app,qid,'edit_item',room_id=living,item_id=full,name='TV half wall',type='PANELLING_HALF',subtype='plain',mdf_id='mdf-9mm',ledge_width=18,position=1,**dict(HALF,height='')).status_code==302
    with app.app_context():
        item=db.session.get(WorkItem,full);q=db.session.get(Quote,qid)
        assert not item.result['valid'] and item.result['groups']=={} and item.pricing_result=={}
        assert not q.result['valid'] and q.result['final_price'] is None
        assert db.session.get(WorkItem,stair).result==unchanged
    assert post_quote(client,app,qid,'delete_item',room_id=living,item_id=full).status_code==302
    assert post_quote(client,app,qid,'edit_room',room_id=living,name='Dining room',notes='New layout',position=2).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid);old_material_cost=q.result['stock_material_cost'];assert q.result['valid']
        assert db.session.get(Room,living).name=='Dining room'
    assert post_quote(client,app,qid,'refresh_prices').status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid);assert q.snapshot!=snapshot
        assert q.result['stock_material_cost']>old_material_cost
    assert post_quote(client,app,qid,'delete_room',room_id=living).status_code==302
    with app.app_context():
        assert db.session.get(WorkItem,half) is None
        assert db.session.get(WorkItem,stair) is not None
        q=db.session.get(Quote,qid)
        assert q.result['valid'] and q.result['required_panelling_m']==7.88
        assert q.result['materials'][0]['required_m']==7.88


def test_metadata_customer_catalogue_and_pages(app,signed_in):
    client=signed_in;qid=create_quote(client,app)
    with app.app_context():cid=db.session.get(Quote,qid).customer_id
    assert client.post(f'/customers/{cid}',data={'name':'Renamed Customer','email':'new@example.test','telephone':'5678','address':'2 Road','postcode':'TT2','notes':'Saved'}).status_code==302
    assert post_quote(client,app,qid,'details',customer_id=cid,title='Updated quote',status='Accepted',full_days=2,extra_hours=3,measure_at='2026-10-01T10:30',quote_date='2026-09-12',accepted_date='2026-09-13',planned_job_date='2026-10-10',notes='Ready').status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid);assert q.status=='Accepted' and q.measure_at.hour==10
        assert q.result['final_price']==0  # empty quote doesn't charge time
        m=db.session.get(Material,'mdf-9mm');data=m.as_dict();data.update(price=99,material_id=m.id,active='on')
        prices=dict(db.session.get(PricingConfig,1).values)
    assert client.post('/materials',data=data).status_code==302
    prices['kerf']=0
    assert client.post('/materials',data=dict(action='pricing',**prices)).status_code==302
    for path in ['/', '/quotes', '/quotes?status=Accepted&q=Renamed', '/customers',f'/customers/{cid}','/quotes/new',f'/quotes/new?customer_id={cid}',f'/quotes/{qid}','/materials','/settings']:
        response=client.get(path);assert response.status_code==200, path
    with app.app_context():
        assert db.session.get(Material,'mdf-9mm').price==99
        assert db.session.get(PricingConfig,1).values['kerf']==0
        seed();assert db.session.get(Material,'mdf-9mm').price==99
        assert db.session.get(PricingConfig,1).values['kerf']==0
    assert client.post('/materials',data=dict(action='pricing',**dict(prices,kerf=-1))).status_code==200


def test_stale_revision_and_foreign_room_rejected(app,signed_in):
    client=signed_in;q1=create_quote(client,app);q2=create_quote(client,app)
    room=add_room(client,app,q1,'Private room')
    assert post_quote(client,app,q2,'delete_room',room_id=room).status_code==404
    assert client.post(f'/quotes/{q1}',data={'action':'add_room','name':'Stale','revision':0}).status_code==409
    with app.app_context():assert db.session.get(Room,room) is not None


def test_actual_migration_and_idempotent_seed(tmp_path):
    application=create_app({'TESTING':True,'SECRET_KEY':'migration-test','SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'migrated.db')})
    runner=application.test_cli_runner()
    first=runner.invoke(args=['init-db']);assert first.exit_code==0,first.output
    second=runner.invoke(args=['init-db']);assert second.exit_code==0,second.output
    with application.app_context():
        assert db.session.scalar(db.select(db.func.count(Material.id)))==31
        assert db.session.get(PricingConfig,1).values['kerf']==3
        assert db.session.scalar(db.select(db.func.count(User.id)))==0
        assert db.session.get(Material,'dado-45mm-3m').preferred_stock_mm==3000
