from app.models import db, Quote, Consumable, OwnedStock
from test_application import create_quote, add_room, add_item, post_quote
from test_calculations import FULL


def test_quote_extras_procurement_owned_stock_and_payments(app, signed_in):
    qid=create_quote(signed_in,app);room=add_room(signed_in,app,qid,'Living room')
    add_item(signed_in,app,qid,room,'Feature wall','PANELLING_FULL',FULL)
    with app.app_context():
        q=db.session.get(Quote,qid)
        material_id=q.result['materials'][0]['material_id']
        calculated=q.result['materials'][0]['calculated_quantity']
        unit=q.result['materials'][0]['unit_price']
        consumable=Consumable(label='Fixing pack',unit_label='pack',price=31,active=True)
        db.session.add(consumable);db.session.commit();consumable_id=consumable.id
    assert post_quote(signed_in,app,qid,'set_extra_material',material_id=material_id,extra_quantity=2).status_code==302
    assert post_quote(signed_in,app,qid,'add_consumable',consumable_id=consumable_id,quantity=1).status_code==302
    assert post_quote(signed_in,app,qid,'add_charge',description='Access charge',amount=20).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid);row=next(r for r in q.result['materials'] if r['material_id']==material_id)
        assert (row['calculated_quantity'],row['extra_quantity'],row['total_quantity'])==(calculated,2,calculated+2)
        assert q.result['consumable_cost']==31 and q.result['additional_charge_cost']==20
        stock=OwnedStock(material_id=material_id,usable_length_mm=1200,quantity=1,note='Existing offcut')
        db.session.add(stock);db.session.commit();stock_id=stock.id
        charge_before=q.result['chargeable_material_cost']
    assert post_quote(signed_in,app,qid,'allocate_owned_stock',material_id=material_id,owned_stock_id=stock_id,quantity=1).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid);row=next(r for r in q.result['materials'] if r['material_id']==material_id)
        assert row['allocated_owned_quantity']==1
        assert row['need_to_purchase_quantity']==calculated+1
        assert q.result['chargeable_material_cost']==charge_before
        deposit=q.result['deposit_required']
        assert deposit % 10==0
    assert post_quote(signed_in,app,qid,'add_payment',amount=deposit,paid_at='2026-09-19',kind='Deposit',note='Received').status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid)
        assert q.result['paid_total']==deposit
        assert q.result['payment_status']=='Part paid' or q.result['payment_status']=='Paid in full'
        assert q.consumables[0].unit_price==31
    assert signed_in.get('/').status_code==200
    assert signed_in.get('/owned-stock').status_code==200
