from copy import deepcopy

import pytest
from flask_migrate import upgrade
from sqlalchemy import text

from app import create_app
from app.models import db, Customer, Quote, Room, WorkItem, JobMaterialState, OwnedStock, OwnedStockAllocation
from app.services.quotes import current_snapshot, recalculate_item, reaggregate, material_plan
from app.services.dimensional_extras import with_dimensional_extras, strip_payload
from app.services.spare_material import recommendations, exact_plan
from app.services.stock_plans import prepare_stock_views, render_sheet_rip_plan
from app.calculations.packing import CalculationError
from test_wall_plans import REPRESENTATIVE_STAIR
from test_application import post_quote


def make_quote(kinds=('stair',)):
    q=Quote(customer=Customer(name='Spare test customer'), title='Spare test', snapshot=current_snapshot(),full_days=0,extra_hours=0)
    for i,kind in enumerate(kinds):
        room=Room(name=f'Room {i+1}',position=i)
        if kind=='stair':
            item=WorkItem(name='Exact stair',type='PANELLING_STAIR_HALF',subtype='plain',
                inputs=dict(REPRESENTATIVE_STAIR),options={'mdf_id':'mdf-9mm'})
        elif kind in ('dado','recovery'):
            item=WorkItem(name='Dado',type='DADO_STRAIGHT',subtype='Dado',
                inputs={'wall_length':2900 if kind=='dado' else 700,'dado_height':1000},options={'dado_rail_id':'dado-45mm-3m'})
        elif kind=='invalid':
            item=WorkItem(name='Invalid profile',type='DADO_STAIR',subtype='Dado Squares Bottom',
                inputs=dict(REPRESENTATIVE_STAIR,bottom_squares=4,bottom_zone_height=1000,gap_width=100),
                options={'dado_rail_id':'dado-45mm-3m','dado_square_id':'dado-45mm-3m'})
        else:
            item=WorkItem(name='Straight wall',type='PANELLING_FULL',subtype='plain',
                inputs=dict(wall_length=1010,height=2440,horizontal_squares=9,vertical_squares=1,slat_width=100),
                options={'mdf_id':'mdf-9mm'})
        room.items.append(item);q.rooms.append(room)
    db.session.add(q);db.session.flush()
    for room in q.rooms:
        for item in room.items:recalculate_item(item,q.snapshot)
    reaggregate(q);db.session.commit()
    return q


def extra(q,quantity,room_index=0,width=100):
    state=JobMaterialState(material_id='mdf-9mm',room_id=q.rooms[room_index].id,extra_quantity=0,
        dimensional_extras=[strip_payload(q.snapshot['catalogue']['mdf-9mm'],width,2440,quantity)])
    q.material_states.append(state);reaggregate(q);db.session.commit();return state


def rip_count(q,room_id=None):
    return sum(len(s['cuts']) for s in q.result['room_stocks'] if s['category']=='mdf' and
               (room_id is None or s['room_id']==room_id))


def test_stair_advisory_preview_same_sheet_and_exact_cuts_untouched(app):
    with app.app_context():
        q=make_quote();before=deepcopy(q.result);cuts=deepcopy(q.rooms[0].items[0].result)
        rec=recommendations(q)[0]
        assert rec['kind']=='rectangular_strip' and rec['quantity']==2
        assert rec['priority']=='MEDIUM' and any('Stair' in reason for reason in rec['reasons'])
        assert rec['current_requirement']==7 and rec['current_stock_count']==1
        assert [p['additional_stock'] for p in rec['previews']]==[0,0]
        assert rec['previews'][1]['used_widths']==[924]
        assert rec['previews'][1]['remainders']==[296]
        assert all(p['incremental_cost']==0 for p in rec['previews'])
        assert q.result==before and q.rooms[0].items[0].result==cuts and not q.material_states
        assert recommendations(q)==[rec]


@pytest.mark.parametrize('quantity',[1,2])
def test_accept_individual_strip_quantities_and_no_fake_sheet_charge(app,signed_in,quantity):
    with app.app_context():
        q=make_quote();qid=q.id;rid=q.rooms[0].id;rec=recommendations(q)[0]
        before=deepcopy(q.result);cuts=deepcopy(q.rooms[0].items[0].result)
    assert post_quote(signed_in,app,qid,'add_recommended_spares',room_id=rid,**{'spare_'+rec['id']:quantity}).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid);state=q.material_states[0]
        assert state.extra_quantity==0 and state.dimensional_extras[0]['quantity']==quantity
        assert rip_count(q)==7+quantity and len(q.result['room_stocks'])==1
        strip_charge=quantity*q.snapshot['pricing']['cut_cost_per_strip']
        assert q.result['chargeable_material_cost']==before['chargeable_material_cost']+strip_charge
        assert q.result['cut_cost']==before['cut_cost']+strip_charge
        assert q.result['stock_material_cost']==before['stock_material_cost']
        for key in ('mastic_units','mastic_cost','labour_cost','take_home','delivery_cost'):
            assert q.result[key]==before[key]
        assert q.rooms[0].items[0].result==cuts
        remaining=recommendations(q)
        assert (remaining[0]['quantity'] if remaining else 0)==2-quantity
        assert q.result['extra_material_cost']==0
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert 'Extra strip · 100×2440 mm' in page and 'Whole-product extra' in page
    assert 'No additional sheet required' in page or quantity==2


def test_sheet_threshold_cost_remove_and_prep_svg(app,signed_in):
    with app.app_context():
        q=make_quote();before=deepcopy(q.result);state=extra(q,6);qid=q.id;sid=state.id
        assert rip_count(q)==13 and len(q.result['room_stocks'])==2
        price=q.snapshot['catalogue']['mdf-9mm']['price']
        assert q.result['dimensional_extra_cost']==price
        assert q.result['extra_material_cost']==price
        assert q.result['chargeable_material_cost']==before['chargeable_material_cost']+price+6*q.snapshot['pricing']['cut_cost_per_strip']
        row=material_plan(q)[0]
        assert row['calculated_quantity']==1 and row['total_quantity']==2 and row['extra_quantity']==0
        assert row['need_to_purchase_quantity']==2
        views=prepare_stock_views(q.result['room_stocks'],q.rooms)
        assert len(views)==2 and sum(len(v['strips']) for v in views)==13
        assert all(render_sheet_rip_plan(v,q.snapshot['catalogue']['mdf-9mm']).count('data-kind="prepared"')==len(v['strips']) for v in views)
    assert post_quote(signed_in,app,qid,'set_dimensional_extra',state_id=sid,extra_index=0,quantity=0).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid)
        assert not q.material_states[0].dimensional_extras
        assert rip_count(q)==7 and q.result['chargeable_material_cost']==before['chargeable_material_cost']
        assert q.result['materials'][0]['need_to_purchase_quantity']==1


def test_recommendation_sheet_threshold_and_no_second_planner(app):
    with app.app_context():
        q=make_quote(('tight',));rec=next(r for r in recommendations(q) if r['kind']=='rectangular_strip')
        assert rec['quantity']==1 and rec['previews'][0]['additional_stock']==1
        assert rec['previews'][0]['incremental_cost']==q.snapshot['catalogue']['mdf-9mm']['price']
        p=strip_payload(q.snapshot['catalogue']['mdf-9mm'],100,2440,1)
        simulation=with_dimensional_extras(q,exact_plan(q),{(q.rooms[0].id,'mdf-9mm'):[p]})
        extra(q,1)
        assert q.result['room_stocks']==simulation['room_stocks']


def test_linear_tight_dado_recovery_and_acceptance(app,signed_in):
    with app.app_context():
        q=make_quote(('dado','recovery'));qid=q.id;before=deepcopy(q.result)
        recs=recommendations(q)
        assert len(recs)==1 and recs[0]['room_id']==q.rooms[0].id
        rec=recs[0];rid=rec['room_id'];price=q.snapshot['catalogue'][rec['material_id']]['price']
        assert rec['kind']=='stock_length' and rec['quantity']==1 and rec['length_mm']==3000
        assert rec['previews'][0]['incremental_cost']==price
        assert any('cannot reproduce' in reason for reason in rec['reasons'])
        assert q.result==before
    assert post_quote(signed_in,app,qid,'add_recommended_spares',room_id=rid,**{'spare_'+rec['id']:1}).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid)
        assert q.material_states[0].extra_quantity==1 and q.material_states[0].dimensional_extras is None
        assert not recommendations(q)
        assert q.result['chargeable_material_cost']==before['chargeable_material_cost']+price
        rows=material_plan(q)
        assert next(r for r in rows if r['room_id']==rid and r['category']=='dado')['extra_quantity']==1
        assert all(r['extra_quantity']==0 for r in rows if r['room_id']!=rid)


def test_invalid_geometry_never_generates_spares(app):
    with app.app_context():
        q=make_quote(('invalid',))
        assert not q.rooms[0].items[0].result['valid']
        assert 'collapses' in q.rooms[0].items[0].result['errors'][0]
        assert not recommendations(q)


def test_duplicate_replay_and_quantity_bounds(app,signed_in):
    with app.app_context():
        q=make_quote();qid=q.id;rid=q.rooms[0].id;rec=recommendations(q)[0]
    data={'spare_'+rec['id']:2}
    assert post_quote(signed_in,app,qid,'add_recommended_spares',room_id=rid,**data).status_code==302
    # New revision but no remaining offer: no duplicate demand is accepted.
    response=post_quote(signed_in,app,qid,'add_recommended_spares',room_id=rid,**data)
    assert response.status_code==200 and 'Choose a quantity' in response.get_data(as_text=True)
    with app.app_context():
        q=db.session.get(Quote,qid)
        assert rip_count(q)==9 and q.material_states[0].dimensional_extras[0]['quantity']==2


def test_room_ownership_and_owned_procurement_only(app):
    with app.app_context():
        q=make_quote(('stair','stair'));before=deepcopy(q.result)
        extra(q,6,0)
        assert rip_count(q,q.rooms[0].id)==13 and rip_count(q,q.rooms[1].id)==7
        assert len(q.result['room_stocks'])==3
        recs=recommendations(q)
        assert all(r['room_id']==q.rooms[1].id for r in recs)
        charge=q.result['chargeable_material_cost']
        owned=OwnedStock(material_id='mdf-9mm',stock_type='full',quantity=1,reserved_quantity=1)
        db.session.add(owned);db.session.flush()
        qid=q.id
        db.session.add(OwnedStockAllocation(quote_id=q.id,room_id=q.rooms[0].id,material_id='mdf-9mm',owned_stock_id=owned.id,quantity=1))
        reaggregate(q)
        assert q.result['chargeable_material_cost']==charge
        assert sum(row['need_to_purchase_quantity'] for row in material_plan(q) if row['category']=='mdf')==2


def test_old_whole_product_extras_unchanged(app,signed_in):
    with app.app_context():
        q=make_quote();base=deepcopy(q.result);state=JobMaterialState(room_id=q.rooms[0].id,material_id='mdf-9mm',extra_quantity=2)
        q.material_states.append(state);reaggregate(q);db.session.commit();qid=q.id
        assert state.dimensional_extras is None and rip_count(q)==7
        assert q.result['cut_cost']==base['cut_cost']
        price=q.snapshot['catalogue']['mdf-9mm']['price']
        assert q.result['extra_material_cost']==2*price
        assert q.result['chargeable_material_cost']==base['chargeable_material_cost']+2*price
        assert material_plan(q)[0]['total_quantity']==3 and material_plan(q)[0]['need_to_purchase_quantity']==3
        assert not recommendations(q)
    assert 'Whole-product extra' in signed_in.get(f'/quotes/{qid}').get_data(as_text=True)


def test_payload_rejects_wrong_material_dimensions_and_fractional_quantity(app):
    with app.app_context():
        q=make_quote();catalogue=q.snapshot['catalogue']
        for product,width,length,quantity in [(catalogue['dado-45mm-3m'],100,3000,1),
            (catalogue['mdf-9mm'],1300,2440,1),(catalogue['mdf-9mm'],100,1000,1),
            (catalogue['mdf-9mm'],100,2440,1.5)]:
            with pytest.raises(CalculationError):strip_payload(product,width,length,quantity)


def test_additive_migration_preserves_old_extra_record(tmp_path):
    app=create_app({'TESTING':True,'SECRET_KEY':'migration-test','SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'migration.db')})
    with app.app_context():
        upgrade(revision='g30_work_item_photos_receipts')
        db.session.execute(text("INSERT INTO customer (id,name) VALUES (1,'Old customer')"))
        db.session.execute(text("INSERT INTO quote (id,customer_id,title,status,created_at,updated_at,full_days,extra_hours,notes,snapshot,result,revision) VALUES (1,1,'Old quote','Draft',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,0,0,'','{}','{}',1)"))
        db.session.execute(text("INSERT INTO job_material_state (id,quote_id,material_id,room_id,extra_quantity) VALUES (1,1,'mdf-9mm',NULL,2)"))
        db.session.commit();upgrade()
        row=db.session.execute(text('SELECT extra_quantity,dimensional_extras FROM job_material_state WHERE id=1')).one()
        assert tuple(row)==(2,None)
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()=='h31_dimensional_extra_material'


def test_selection_is_independent_across_materials_and_rooms(app,signed_in):
    with app.app_context():
        q=make_quote(('stair','dado'));qid=q.id;recs=recommendations(q)
        mdf=next(r for r in recs if r['kind']=='rectangular_strip')
        dado=next(r for r in recs if r['kind']=='stock_length')
    assert post_quote(signed_in,app,qid,'add_recommended_spares',room_id=mdf['room_id'],
        **{'spare_'+mdf['id']:1,'spare_'+dado['id']:1}).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid)
        assert len(q.material_states)==1 and q.material_states[0].room_id==mdf['room_id']
        assert any(r['id']==dado['id'] for r in recommendations(q))
        assert next(r for r in recommendations(q) if r['id']==mdf['id'])['quantity']==1
    assert post_quote(signed_in,app,qid,'add_recommended_spares',room_id=mdf['room_id'],
        **{'spare_'+mdf['id']:2}).status_code==200
    with app.app_context():assert db.session.get(Quote,qid).material_states[0].dimensional_extras[0]['quantity']==1


def test_simple_good_recovery_has_no_spare_offer(app):
    with app.app_context():
        q=make_quote(('recovery',))
        assert q.result['valid'] and not recommendations(q)


def test_multiple_widths_share_same_extra_record_without_losing_dimensions(app):
    with app.app_context():
        q=make_quote();state=extra(q,1)
        state.dimensional_extras=state.dimensional_extras+[strip_payload(q.snapshot['catalogue']['mdf-9mm'],150,2440,1)]
        reaggregate(q)
        cuts=[c for s in q.result['room_stocks'] for rip in s['cuts'] for c in rip['finished_cuts'] if c.get('is_dimensional_extra')]
        assert sorted(c['width_mm'] for c in cuts)==[100,150]
        assert len(q.material_states)==1 and len(q.result['room_stocks'])==1


def test_cabinet_no_default_spare_sheet_and_pse_uses_linear_spare(app):
    from test_cabinet_refinements import cabinet
    with app.app_context():
        q=make_quote(('recovery',));room=q.rooms[0]
        room.items.clear();item=WorkItem(name='PSE Cabinet',type='CABINET',subtype='plain',inputs={},options={})
        room.items.append(item);db.session.flush()
        item.result=cabinet(q.snapshot['catalogue'],q.snapshot['pricing'],item_id=str(item.id),
            inputs={'opening_width':2200},options={'worktop_type':'pse','pse_material_id':'pse-100x25-2.4m'})
        reaggregate(q);before=deepcopy(item.result)
        recs=recommendations(q)
        assert not any(q.snapshot['catalogue'][r['material_id']]['category']=='mdf' for r in recs)
        pse=next(r for r in recs if r['material_id']=='pse-100x25-2.4m')
        assert pse['kind']=='stock_length' and pse['quantity']==1
        assert item.result==before


def test_bead_and_coving_share_linear_recovery_policy_without_changing_cuts(app):
    with app.app_context():
        q=make_quote();item=q.rooms[0].items[0]
        item.subtype='bead';item.options=dict(mdf_id='mdf-9mm',bead_id='bead-glass_bead-9x9')
        recalculate_item(item,q.snapshot)
        coving=WorkItem(name='External Coving',type='COVING',subtype='plain',
            inputs={'wall_length':2700,'start_corner':'External','end_corner':'External'},options={})
        q.rooms[0].items.append(coving);db.session.flush();recalculate_item(coving,q.snapshot);reaggregate(q)
        before=[deepcopy(i.result) for i in q.rooms[0].items]
        recs=recommendations(q)
        assert any(q.snapshot['catalogue'][r['material_id']]['category']=='bead' for r in recs)
        assert any(q.snapshot['catalogue'][r['material_id']]['category']=='coving' for r in recs)
        assert [i.result for i in q.rooms[0].items]==before
