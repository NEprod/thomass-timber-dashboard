from copy import deepcopy
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from app.calculations.sections import calculate
from app.calculations.room_stock import pack_rooms as pack_room_stock
from app.calculations.pricing import aggregate
from app.services.stock_plans import prepare_stock_views, render_sheet_rip_plan, render_linear_stock_plan
from app.models import db, Quote
from test_application import create_quote, add_room, add_item, post_quote
from test_calculations import OPTIONS
from test_wall_plans import REPRESENTATIVE_STAIR
from test_cabinet import _cabinet_options


def room(*results, room_id=1):
    return dict(id=room_id, name=f'Room {room_id}', items=[dict(id=str(i), name=f'Wall {i}', result=r) for i,r in enumerate(results,1)])


def pack_rooms(*args):
    materials, stocks=pack_room_stock(*args)
    return dict(materials=materials,room_stocks=stocks)


def elements(svg, kind):
    root=ET.fromstring(svg)
    assert root.attrib['preserveAspectRatio']=='xMidYMid meet'
    assert '<title>' in svg and '<desc>' in svg
    return [node for node in root.iter() if node.attrib.get('data-kind')==kind]


def rip_demand(count):
    # Each whole-length cut requires exactly one full rip; the real room packer
    # assigns these rips to raw sheets. This is not a display-only sheet fixture.
    return dict(valid=True, groups={'vertical':dict(material_id='mdf-9mm',width_mm=100,
        cuts=[dict(id=str(i),material_id='mdf-9mm',length_mm=2440,width_mm=100,
                   label=f'Vertical {i}',role='Vertical',work_item_id='1') for i in range(count)])})


@pytest.mark.parametrize(('count','sheets'),[(8,1),(14,2)])
def test_authoritative_full_sheet_rips_and_multisheet_identity(catalogue,count,sheets):
    packed=pack_rooms([room(rip_demand(count))],catalogue,3)
    stocks=packed['room_stocks']; before=deepcopy(packed)
    views=prepare_stock_views(stocks)
    assert len(views)==sheets
    strips=[]
    for view in views:
        stock=view['source']; svg=render_sheet_rip_plan(view,catalogue['mdf-9mm'])
        assert float(elements(svg,'stock')[0].attrib['width'])==2440
        assert float(elements(svg,'stock')[0].attrib['height'])==1220
        assert len(elements(svg,'prepared'))==len(stock['cuts'])
        assert len(elements(svg,'kerf'))==len(stock['cuts'])-1
        assert float(elements(svg,'remainder')[0].attrib['height'])==stock['remainder_mm']
        assert [segment['source']['id'] for segment in view['segments']]==[rip['id'] for rip in stock['cuts']]
        strips.extend(segment['number'] for segment in view['segments'])
        for plan in view['strips']:
            assert len(plan['segments'])==1 and plan['segments'][0]['size_mm']==2440
    assert strips==list(range(1,count+1))
    assert packed['materials'][0]['new_purchase_units']==sheets
    assert packed==before
    if count==8:
        assert stocks[0]['used_mm']==821 and stocks[0]['kerf_loss_mm']==21
        assert stocks[0]['remainder_mm']==399


def test_stair_prepare_cut_assignments_installed_metadata_and_safe_labels(catalogue):
    result=calculate('PANELLING_STAIR_HALF','plain',REPRESENTATIVE_STAIR,OPTIONS,catalogue,3,'1')
    packed=pack_rooms([room(result)],catalogue,3); before=deepcopy((result,packed))
    source_rooms=[SimpleNamespace(items=[SimpleNamespace(result=result)])]
    view=prepare_stock_views(packed['room_stocks'],source_rooms)[0]
    assert result['geometry']['wall_layout']['installed_panel_height_mm']==1000
    cuts=[]
    for plan,rip in zip(view['strips'],view['source']['cuts']):
        assert [s['source'] for s in plan['segments']]==rip['finished_cuts']
        svg=render_linear_stock_plan(plan,'Strip <unsafe> & stock')
        assert '&lt;unsafe&gt;' in svg and '<unsafe>' not in svg
        assert [float(e.attrib['width']) for e in elements(svg,'cut')]==pytest.approx([c['length_mm'] for c in rip['finished_cuts']],abs=.01)
        assert [float(e.attrib['x']) for e in elements(svg,'kerf')]==pytest.approx([k['position_mm'] for k in plan['kerfs']],abs=.01)
        assert plan['used_mm']+plan['remainder_mm']==2440
        cuts.extend(plan['segments'])
    assert any(s['size_mm']==2440 for s in cuts)
    assert sum(s['size_mm']==pytest.approx(804.89996) and s['installed_length_mm']==680 for s in cuts)==3
    assert sorted(s['source']['id'] for s in cuts)==sorted(c['id'] for group in result['groups'].values() for c in group['cuts'])
    assert (result,packed)==before


@pytest.mark.parametrize('family',['dado','bead','coving'])
def test_shared_linear_svg_keeps_authoritative_plan_and_price(catalogue,seed_data,family):
    if family=='dado':
        results=[calculate('DADO_STRAIGHT','Dado',{'wall_length':n,'dado_height':1000}, {'dado_rail_id':'dado-45mm-3m'},catalogue,3,str(i)) for i,n in enumerate((1800,1100),1)]
    elif family=='bead':
        results=[calculate('PANELLING_HALF','bead',dict(wall_length=3000,height=1000,horizontal_squares=4,vertical_squares=1,slat_width=100),dict(OPTIONS,bead_id='bead-glass_bead-9x9'),catalogue,3,'1')]
    else:
        results=[calculate('COVING','plain',dict(wall_length=n,start_corner='Internal',end_corner='Internal'),{},catalogue,3,str(i)) for i,n in enumerate((1800,1700),1)]
    rooms=[room(*results)]
    priced=aggregate(results,catalogue,seed_data['pricing'],rooms=rooms); before=deepcopy(priced)
    stocks=[s for s in priced['room_stocks'] if s['category']==family]
    assert stocks
    views=prepare_stock_views(stocks)
    for view,stock in zip(views,stocks):
        svg=render_linear_stock_plan(view,'Stock Length')
        assert [float(e.attrib['width']) for e in elements(svg,'cut')]==[c['length_mm'] for c in stock['cuts']]
        assert float(elements(svg,'stock')[0].attrib['width'])==stock['stock_length_mm']
        assert float(elements(svg,'remainder')[0].attrib['width'])==stock['remainder_mm']
        assert sum(k['size_mm'] for k in view['kerfs'])==stock['kerf_loss_mm']
    assert priced==before
    if family=='coving':assert len(stocks)==1 and stocks[0]['stock_length_mm']==3600
    if family=='dado':assert len(stocks)==1 and stocks[0]['stock_length_mm']==3000


def test_room_boundaries_and_dado_square_existing_material_mode(catalogue):
    result=calculate('DADO_STRAIGHT','Dado Squares Bottom',dict(wall_length=3000,gap_width=100,bottom_squares=4,bottom_zone_height=1000),dict(dado_rail_id='dado-45mm-3m',dado_square_id='dado-45mm-3m'),catalogue,3,'1')
    packed=pack_rooms([room(result),room(result,room_id=2)],catalogue,3)
    assert {s['room_id'] for s in packed['room_stocks']}=={1,2}
    # Current supported square profiles are purchased dado, not MDF rips. Keep
    # their mode authoritative rather than inventing a sheet preparation step.
    assert all(s['category']=='dado' for s in packed['room_stocks'])
    assert result['geometry']['wall_layout'] and result['geometry']['layout_height_mm']==1000
    for rid in (1,2):
        views=prepare_stock_views([s for s in packed['room_stocks'] if s['room_id']==rid])
        assert views[0]['number']==1 and all(v['mode']=='linear' for v in views)


def test_quote_rendering_does_not_mutate_plan_and_cabinet_uses_existing_sheet_template(app,signed_in):
    qid=create_quote(signed_in,app); rid=add_room(signed_in,app,qid,'Visual room')
    add_item(signed_in,app,qid,rid,'Stair wall','PANELLING_STAIR_HALF',REPRESENTATIVE_STAIR)
    # Save a current Cabinet through its normal route alongside the strip wall.
    iid=add_item(signed_in,app,qid,rid,'Cabinet','CABINET',{})
    assert post_quote(signed_in,app,qid,'edit_item',room_id=rid,item_id=iid,name='Cabinet',type='CABINET',subtype='plain',position=1,
        opening_width=1800,unit_width=1600,unit_height=800,unit_depth=450,divider_count=1,divider_height=782,shelves_per_bay=1,door_count=2,front_overhang=20,workshop_hours=4,installation_days=1,
        **_cabinet_options(back_enabled=True)).status_code==302
    with app.app_context():
        q=db.session.get(Quote,qid); before=deepcopy(q.result)
        sheets=[s for s in q.result['room_stocks'] if s.get('packing_kind')=='sheet']
        assert len({s['material_id'] for s in sheets})==2
        views=[v for v in prepare_stock_views(q.result['room_stocks']) if v['mode']=='sheet']
        assert [v['number'] for v in views]==list(range(1,len(sheets)+1))
        assert all(v['total']==len(sheets) for v in views)
    for _ in range(2):
        page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
        assert 'Workshop Preparation' in page and 'Cut Plan' in page and 'stock-plan-svg' in page
        assert 'Base cut 804.9' in page and 'Installed centreline 680' in page
        assert 'Guillotine sheet plan' in page and 'Sheet Cut Plan' in page
        assert 'Installed height 1000 mm' in page
    with app.app_context():assert db.session.get(Quote,qid).result==before
