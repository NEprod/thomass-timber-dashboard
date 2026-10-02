"""Quote display follows packed stock and saved finances without changing them."""
from copy import deepcopy
from datetime import date
from xml.etree import ElementTree as ET

import pytest

from app.models import db, Quote, Room, WorkItem, Payment
from app.services.quotes import recalculate_item, reaggregate
from app.services.quote_presentation import quote_presentation, opening_examples, cut_display_label
from app.services.cut_summaries import cut_summary
from app.services.wall_plans import render_wall_plan
from test_strip_cut_charge import representative
from test_spare_material import make_quote, extra
from test_calculations import FULL, HALF


def add_work(q, kind, inputs, options=None, subtype='plain', name='Display test'):
    room = Room(name=name, position=len(q.rooms))
    item = WorkItem(name=name, type=kind, subtype=subtype, inputs=inputs,
                   options=options or {'mdf_id':'mdf-9mm'})
    room.items.append(item); q.rooms.append(room); db.session.flush()
    recalculate_item(item,q.snapshot); reaggregate(q); db.session.commit()
    assert item.result['valid'], item.result.get('errors')
    return item


def test_stair_calculated_spare_total_charge_hierarchy_and_read_only(app,signed_in):
    with app.app_context():
        q=representative(); extra(q,2)
        qid=q.id; iid=q.rooms[0].items[0].id
        before=deepcopy(q.result); cuts=deepcopy(q.rooms[0].items[0].result)
        display=quote_presentation(q)
        assert display['requirements'][iid][0]['quantity']==8
        prep=display['workshop'][0]
        assert prep['rows']==[dict(width_mm=100,length_mm=2440,calculated=8,
            extra=2,total=10,cut_charge=20)]
        assert (prep['sheets'],prep['additional_sheets'],prep['rate'])==(1,0,2)
        assert sum(p['spare'] for p in display['cutting'][0]['plans'])==2
        assert q.result==before and q.rooms[0].items[0].result==cuts
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert '8 × 100×2440 mm calculated strips' in page
    assert 'TOTAL TO PREPARE: 10 × 100×2440 mm' in page
    assert 'Strip cutting: 10 × £2.00 = <strong>£20.00</strong>' in page
    assert 'Raw sheets required: <strong>1</strong>' in page
    assert 'Horizontal / vertical strips' not in page
    assert 'Top / bottom displayed settings' not in page
    assert 'Angled mitres — top / bottom' in page and 'Slope mitre' in page
    assert 'Flat 2 · Angled 3 · Transition 2' in page
    item=page.split(f'id="item-{iid}"')[1].split('Remove work item')[0]
    assert item.index('Work item photos')<item.index('Calculated Requirements')<item.index('Wall Layout')<item.index('Cut Summary')
    assert '<summary>Installed Dimensions' in item
    installed=item.split('<summary>Installed Dimensions')[0].rsplit('<details',1)[1]
    assert ' open' not in installed
    notes=item.index('Calculation notes')
    assert item.index('Slope angle')>notes and item.index('item labour')>notes
    assert 'data-opening="Opening 2.1"' in item and 'Opening 2.1 · Transition' in item
    order=['id="recommended-spares"','<h3>Quote consumables','<h3>Additional charges',
           'id="workshop-preparation"','id="room-cut-plan"','id="quoted-materials"',
           'id="quotation-total"','id="purchasing-admin"','id="receipts"','<h3>Customer payments']
    positions=[page.index(s) for s in order]; assert positions==sorted(positions)
    assert page.count('id="recommended-spares"')==1 and page.count('id="room-cut-plan"')==1
    assert '— Spare · 100×2440 mm' in page
    assert 'Extra strip · 100×2440 mm' in page
    with app.app_context():
        q=db.session.get(Quote,qid)
        assert q.result==before and q.rooms[0].items[0].result==cuts


@pytest.mark.parametrize(('kind','inputs'), [('PANELLING_FULL',FULL),('PANELLING_HALF',HALF)])
def test_straight_requirements_match_packed_room_without_stair_noise(app,signed_in,kind,inputs):
    with app.app_context():
        q=make_quote(('recovery',));item=add_work(q,kind,dict(inputs))
        display=quote_presentation(q);row=display['requirements'][item.id][0]
        prep=next(g for g in display['workshop'] if g['room'].id==item.room_id)
        assert row['quantity']==sum(len(v['source']['cuts']) for v in prep['views'])
        qid=q.id;iid=item.id;before=deepcopy(q.result)
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    item=page.split(f'id="item-{iid}"')[1].split('Remove work item')[0]
    assert 'Square dimensions' in item and 'Wall Layout' in item
    assert 'Slope mitre' not in item and 'Angled mitres' not in item
    assert 'Horizontal / vertical strips' not in item
    with app.app_context(): assert db.session.get(Quote,qid).result==before


@pytest.mark.parametrize(('kind','subtype','inputs','options'),[
    ('DADO_STRAIGHT','Dado',dict(wall_length=1800,dado_height=1000),dict(dado_rail_id='dado-45mm-3m')),
    ('DADO_STRAIGHT','Dado Squares Bottom',dict(wall_length=3000,gap_width=100,bottom_squares=4,bottom_zone_height=1000),dict(dado_rail_id='dado-45mm-3m',dado_square_id='dado-45mm-3m')),
    ('COVING','plain',dict(wall_length=3400,start_corner='Internal',end_corner='External'),{}),
])
def test_linear_types_reuse_authoritative_stock_without_irrelevant_preparation(app,signed_in,kind,subtype,inputs,options):
    with app.app_context():
        q=make_quote(('recovery',));item=add_work(q,kind,inputs,options,subtype)
        display=quote_presentation(q); rows=display['requirements'][item.id]
        stocks=[s for s in q.result['room_stocks'] if s['room_id']==item.room_id]
        assert sum(r['quantity'] for r in rows)==len(stocks)
        assert all(r['mode']=='linear' for r in rows)
        assert not any(g['room'].id==item.room_id for g in display['workshop'])
        qid=q.id;iid=item.id;before=deepcopy(q.result)
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    result=page.split(f'id="item-{iid}"')[1].split('Remove work item')[0]
    assert 'stock lengths' in result and 'Cut Summary' in result
    assert 'calculated strips' not in result
    assert ('Wall Layout' in result)==(kind!='COVING')
    assert 'Main dado rail' not in result and 'Slope mitre' not in result
    if subtype=='Dado Squares Bottom': assert 'data-opening="Bottom square 1"' in result
    assert 'stock-plan-svg' in page
    with app.app_context(): assert db.session.get(Quote,qid).result==before


@pytest.mark.parametrize('preset',['alcove','window_seat','bench','custom'])
def test_all_cabinet_presets_display_nested_sheets_and_recorded_charge(app,signed_in,preset):
    with app.app_context():
        q=make_quote(('recovery',))
        item=add_work(q,'CABINET',dict(opening_width=1800,unit_width=1600,unit_height=800,unit_depth=450,divider_height=782,
            divider_count=1,shelves_per_bay=1,door_count=0,workshop_hours=4,installation_days=1),
            dict(cabinet_preset=preset,carcass_material_id='mdf-18mm',base_type='none',
                 worktop_type='pse' if preset=='alcove' else 'none',pse_material_id='pse-100x25-2.4m'))
        display=quote_presentation(q)
        groups=[g for g in display['workshop'] if g['room'].id==item.room_id]
        sheets=[s for s in q.result['room_stocks'] if s['room_id']==item.room_id and s.get('packing_kind')=='sheet']
        assert sum(r['quantity'] for r in display['requirements'][item.id] if r['mode']=='sheet')==len(sheets)
        assert sum(g['operations'] for g in groups)==sum(len(s['sheet_cut_lines']) for s in sheets)
        assert sum(g['cut_charge'] for g in groups)==q.result['cut_cost']
        qid=q.id;iid=item.id;before=deepcopy(q.result)
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    result=page.split(f'id="item-{iid}"')[1].split('Remove work item')[0]
    assert 'raw sheets' in result and 'Wall Layout' not in result and 'Slope mitre' not in result
    assert 'Cabinet parts and sheet cut blanks' in result
    assert 'Guillotine sheet plan' in page and 'Border allowance is not charged' in page
    with app.app_context(): assert db.session.get(Quote,qid).result==before


def test_commercial_status_is_saved_and_draft_admin_remains_accessible(app,signed_in):
    with app.app_context():
        q=representative();q.payments.append(Payment(amount=25,kind='Deposit',paid_at=date.today()))
        q.payments.append(Payment(amount=10,kind='Interim',paid_at=date.today()))
        reaggregate(q);db.session.commit();qid=q.id
        assert quote_presentation(q)['deposit_paid']==25
        total=q.result['final_price'];before=deepcopy(q.result)
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert f'<strong>£{total:,.2f}</strong>' in page and f'<div class="total-price">£{total:,.2f}</div>' in page
    assert 'DEPOSIT PAID</small><strong>£25.00' in page
    assert 'id="purchasing-admin" >' in page
    for action in ['add_payment','edit_payment','add_charge','add_consumable','mark_material_purchased','set_extra_material']:
        assert f'name="action" value="{action}"' in page
    with app.app_context():
        q=db.session.get(Quote,qid);q.status='Accepted';db.session.commit()
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert 'id="purchasing-admin" open>' in page
    with app.app_context(): assert db.session.get(Quote,qid).result==before


def test_opening_dimensions_ids_and_mirror_use_existing_vertices(app):
    with app.app_context():
        q=representative();layout=q.rooms[0].items[0].result['geometry']['wall_layout'];before=deepcopy(layout)
        examples=opening_examples(layout)
        assert [e['id'] for e in examples]==['Opening 1.1','Opening 2.1','Opening 3.1','Opening 6.1']
        assert all(e['width']==pytest.approx(457.14,abs=.001) for e in examples)
        right=ET.fromstring(render_wall_plan(layout,'Wall <unsafe>','Right'))
        left=ET.fromstring(render_wall_plan(layout,'Wall <unsafe>','Left'))
        rlabels=[n for n in right if n.get('data-opening')];llabels=[n for n in left if n.get('data-opening')]
        assert len(rlabels)==len(llabels)==7
        for r,l in zip(rlabels,llabels):
            assert r.text==l.text and r.get('data-opening')==l.get('data-opening')
            assert float(r.get('x'))+float(l.get('x'))==pytest.approx(4000,abs=.01)
        assert layout==before


def test_summary_equivalent_horizontal_profiles_keeps_cut_settings_and_piece_identity():
    def piece(edge,angle=45,width=9):
        return dict(label='Original',role='Bead flat square 2 row 1 · '+edge,material_id='bead',width_mm=width,
            length_mm=450,requirement_status='EXACT',angle_information=dict(square=2,row=1,edge=edge,
            profile_segment=1,start_joint_setting=angle,end_joint_setting=angle))
    groups={'bead':dict(cuts=[piece('top'),piece('bottom'),piece('bottom',30),piece('top',width=15)])}
    before=deepcopy(groups);summary=cut_summary(groups)
    assert len(summary)==2 and len(summary[0]['rows'])==2
    assert summary[0]['rows'][0]['quantity']==2 and 'top/bottom' in summary[0]['rows'][0]['role']
    assert cut_display_label(groups['bead']['cuts'][0])=='Square 2.1 · top'
    assert groups==before


def test_shared_room_stock_is_explicit_not_invented_per_item_allocation(app):
    with app.app_context():
        q=make_quote(('recovery',));room=q.rooms[0]
        second=WorkItem(name='Second short Dado',type='DADO_STRAIGHT',subtype='Dado',
            inputs=dict(wall_length=700,dado_height=1000),options=dict(dado_rail_id='dado-45mm-3m'))
        room.items.append(second);db.session.flush();recalculate_item(second,q.snapshot);reaggregate(q)
        display=quote_presentation(q)
        assert len(q.result['room_stocks'])==1
        for item in room.items:
            assert display['requirements'][item.id][0]['quantity']==1
            assert display['requirements'][item.id][0]['shared']
