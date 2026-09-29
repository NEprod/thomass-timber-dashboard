from copy import deepcopy
import pytest

from app.calculations.sections import calculate
from app.calculations.pricing import aggregate
from app.calculations.packing import CalculationError
from app.models import db, Quote, Room, WorkItem, Material, OwnedStock, PricingConfig
from app.services.quotes import current_snapshot, recalculate_item, reaggregate, material_plan
from test_application import create_quote, add_room, post_quote

OPTIONS = {}

@pytest.mark.parametrize(('start','end','expected'), [
    ('Internal','Internal',2400), ('External','Internal',2527),
    ('Internal','External',2527), ('External','External',2654),
])
def test_coving_corner_allowance(catalogue, start, end, expected):
    result=calculate('COVING','plain',dict(wall_length=2400,start_corner=start,end_corner=end),
                     OPTIONS,catalogue,3,'wall-1',10)
    assert result['geometry']['external_allowance_mm']==expected-2400
    assert result['geometry']['finished_cut_length']==expected
    assert sum(c['length_mm'] for g in result['groups'].values() for c in g['cuts'])==expected
    assert result['groups']['coving']['cuts'][0]['work_item_id']=='wall-1'


def _room(room_id, items):
    return dict(id=room_id,name='Living Room',items=items)


def _coving_item(catalogue, idx, length):
    result=calculate('COVING','plain',dict(wall_length=length,start_corner='Internal',end_corner='Internal'),
                     OPTIONS,catalogue,3,str(idx),10)
    return dict(id=str(idx),name=f'Wall {idx}',result=result)


def test_coving_room_packing_kerf_stock_price_and_labels(catalogue, seed_data):
    pricing=deepcopy(seed_data['pricing'])
    items=[_coving_item(catalogue,1,1800),_coving_item(catalogue,2,1100)]
    result=aggregate([i['result'] for i in items],catalogue,pricing,rooms=[_room(1,items)])
    stocks=[s for s in result['room_stocks'] if s['category']=='coving']
    assert len(stocks)==1 and stocks[0]['material_id']=='coving-127x127-3m'
    assert {c['wall_name'] for c in stocks[0]['cuts']}=={'Wall 1','Wall 2'}
    assert stocks[0]['kerf_loss_mm']==10
    assert result['stock_material_cost']==10
    assert result['labour_cost']==18.85
    split=aggregate([items[0]['result'],items[1]['result']],catalogue,pricing,rooms=[_room(1,[items[0]]),_room(2,[items[1]])])
    assert len([s for s in split['room_stocks'] if s['category']=='coving'])==2

    edge=[_coving_item(catalogue,3,1810),_coving_item(catalogue,4,1180)]
    fits=aggregate([i['result'] for i in edge],catalogue,pricing,rooms=[_room(2,edge)])
    assert [s['material_id'] for s in fits['room_stocks'] if s['category']=='coving']==['coving-127x127-3m']
    pricing['coving_kerf']=11
    too_long=aggregate([i['result'] for i in edge],catalogue,pricing,rooms=[_room(2,edge)])
    assert [s['material_id'] for s in too_long['room_stocks'] if s['category']=='coving']==['coving-127x127-3.6m']
    assert too_long['stock_material_cost']==12
    assert calculate('DADO_STRAIGHT','Dado',{'wall_length':1000},{'dado_rail_id':'dado-45mm-3m'},catalogue,pricing['kerf'])['groups']


def test_coving_room_chooses_fewer_lengths_before_shorter_stock(catalogue, seed_data):
    pricing=deepcopy(seed_data['pricing'])
    items=[_coving_item(catalogue,1,1800),_coving_item(catalogue,2,1700)]
    result=aggregate([i['result'] for i in items],catalogue,pricing,rooms=[_room(1,items)])
    stocks=[s for s in result['room_stocks'] if s['category']=='coving']
    assert len(stocks)==1
    assert stocks[0]['stock_length_mm']==3600
    assert stocks[0]['used_mm']==3510
    assert stocks[0]['remainder_mm']==90
    assert {c['wall_name'] for c in stocks[0]['cuts']}=={'Wall 1','Wall 2'}
    assert result['stock_material_cost']==12

    separate=aggregate([i['result'] for i in items],catalogue,pricing,
                       rooms=[_room(1,[items[0]]),_room(2,[items[1]])])
    assert sorted(s['stock_length_mm'] for s in separate['room_stocks'] if s['category']=='coving')==[3000,3000]

    edge=[_coving_item(catalogue,3,1800),_coving_item(catalogue,4,1790)]
    fits=aggregate([i['result'] for i in edge],catalogue,pricing,rooms=[_room(3,edge)])
    assert [s['stock_length_mm'] for s in fits['room_stocks'] if s['category']=='coving']==[3600]
    pricing['coving_kerf']=11
    split=aggregate([i['result'] for i in edge],catalogue,pricing,rooms=[_room(3,edge)])
    assert sorted(s['stock_length_mm'] for s in split['room_stocks'] if s['category']=='coving')==[3000,3000]


def test_coving_long_run_is_one_3600_piece_and_overlength_rejected(catalogue, seed_data):
    result=calculate('COVING','plain',dict(wall_length=3200,start_corner='Internal',end_corner='Internal'),
                     OPTIONS,catalogue,3,'long',10)
    assert result['geometry']['finished_cut_length']==3200
    priced=aggregate([result],catalogue,seed_data['pricing'],rooms=[_room(1,[dict(id='long',name='Long wall',result=result)])])
    assert aggregate([result],catalogue,seed_data['pricing'],days=1,rooms=[_room(1,[dict(id='long',name='Long wall',result=result)])])['take_home']==180
    stock=next(s for s in priced['room_stocks'] if s['category']=='coving')
    assert stock['material_id']=='coving-127x127-3.6m'
    assert stock['cuts'][0]['length_mm']==3200
    with pytest.raises(CalculationError,match='longer than the longest available continuous stock'):
        calculate('COVING','plain',dict(wall_length=3600,start_corner='External',end_corner='Internal'),OPTIONS,catalogue,3,'too-long',10)


def test_coving_workflow_settings_extra_reservation_and_reopen(app, signed_in):
    client=signed_in
    qid=create_quote(client,app)
    rid=add_room(client,app,qid,'Living Room')
    assert post_quote(client,app,qid,'add_item',room_id=rid,name='Window Wall',type='COVING').status_code==302
    with app.app_context():
        item=db.session.scalar(db.select(WorkItem).where(WorkItem.room_id==rid))
        item_id=item.id
    response=post_quote(client,app,qid,'edit_item',room_id=rid,item_id=item_id,name='Window Wall',type='COVING',subtype='plain',wall_length=2400,start_corner='External',end_corner='Internal',position=0)
    assert response.status_code==302
    with app.app_context():
        quote=db.session.get(Quote,qid)
        before=quote.result['chargeable_material_cost']
        assert quote.rooms[0].items[0].result['geometry']['finished_cut_length']==2527
        row=next(r for r in material_plan(quote) if r['category']=='coving')
        material_id=row['material_id']
        stock=db.session.scalar(db.select(Material).where(Material.id=='coving-127x127-3.6m'))
        db.session.add(OwnedStock(material_id=stock.id,stock_type='full',quantity=1))
        db.session.commit();stock_id=db.session.scalar(db.select(OwnedStock.id))
    assert post_quote(client,app,qid,'set_extra_material',room_id=rid,material_id=material_id,extra_quantity=1).status_code==302
    with app.app_context():
        quote=db.session.get(Quote,qid)
        assert quote.result['chargeable_material_cost']==before+quote.snapshot['catalogue'][material_id]['price']
        assert quote.rooms[0].items[0].result['groups']['coving']['cuts'][0]['label']=='Coving run'
        charge_after_extra=quote.result['chargeable_material_cost']
    assert post_quote(client,app,qid,'allocate_owned_stock',room_id=rid,material_id=material_id,owned_stock_id=stock_id,quantity=1).status_code==302
    with app.app_context():
        quote=db.session.get(Quote,qid)
        row=next(r for r in material_plan(quote) if r.get('room_id')==rid and r['material_id']==material_id)
        assert row['need_to_purchase_quantity']==1
    assert post_quote(client,app,qid,'mark_material_purchased',room_id=rid,material_id=material_id,quantity=1).status_code==302
    page=client.get(f'/quotes/{qid}')
    assert page.status_code==200 and b'Finished Coving cut' in page.data and b'127 \xc3\x97 127 Coving' in page.data
    with app.app_context():
        quote=db.session.get(Quote,qid)
        assert quote.rooms[0].items[0].type=='COVING'
        assert quote.snapshot['pricing']['coving_kerf']==10
        assert quote.result['stock_material_cost']==10
        assert quote.result['chargeable_material_cost']==charge_after_extra
        assert quote.purchases[0].room_id==rid
        assert quote.result['take_home'] >= quote.rooms[0].items[0].pricing_result['labour_cost']


def test_coving_pricing_settings_are_editable_and_seed_preserves_values(app, signed_in):
    client=signed_in
    page=client.get('/materials')
    assert page.status_code==200 and b'Coving price per linear metre' in page.data and b'Coving kerf' in page.data
    with app.app_context():
        values=dict(db.session.get(PricingConfig,1).values)
    values.update(coving_kerf=12,coving_per_m_gbp=7.25)
    assert client.post('/materials',data=dict(action='pricing',**values)).status_code==302
    with app.app_context():
        config=db.session.get(PricingConfig,1)
        assert config.values['kerf']==3 and config.values['coving_kerf']==12
        assert config.values['coving_per_m_gbp']==7.25
        from app.seed import seed
        seed()
        assert config.values['coving_kerf']==12 and config.values['coving_per_m_gbp']==7.25
