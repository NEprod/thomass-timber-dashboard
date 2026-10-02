from copy import deepcopy
import math

import pytest

from app.calculations.sections import calculate
from app.calculations.pricing import aggregate
from app.services.cut_summaries import cut_summary
from app.services.wall_plans import render_wall_plan
from app.models import db, Quote
from test_calculations import OPTIONS, HALF, STAIR
from test_application import create_quote, add_room, add_item


MITRE_STAIR = dict(STAIR, wall_length=4500, lower_landing=1000,
                   upper_landing=1000, slope_length=3500)


def cut(length, material='mdf-9mm', width=100, role='Horizontal', quantity=1, **values):
    return dict(material_id=material, width_mm=width, length_mm=length,
                role=role, quantity=quantity, **values)


def test_compact_summary_quantities_and_safe_grouping():
    cuts = [cut(450) for _ in range(10)] + [cut(150) for _ in range(3)]
    cuts += [cut(450, material='bead', width=9), cut(450, width=150),
             cut(450, role='Vertical'), cut(450, angle_information={'start_joint_setting':45})]
    groups = {'horizontal': {'cuts': cuts}}
    before = deepcopy(groups)
    summary = cut_summary(groups)
    assert [(r['quantity'], r['prepare_length_mm']) for r in summary[0]['rows']] == [(10,450),(3,150),(1,450),(1,450)]
    assert len(summary) == 3
    assert groups == before
    assert cut_summary({'vertical':{'cuts':[cut(800, quantity=3)]}})[0]['rows'][0]['quantity'] == 3


def test_dado_square_grouping_removes_locations_but_keeps_edges_and_profiles(catalogue):
    result = calculate('DADO_STRAIGHT','Dado Squares Bottom',
        dict(wall_length=3000,gap_width=100,bottom_squares=4,bottom_zone_height=1000),
        dict(dado_rail_id='dado-45mm-3m',dado_square_id='dado-45mm-3m'),catalogue,3)
    before = deepcopy(result)
    summary = cut_summary(result['groups'])
    rows = [r for family in summary for r in family['rows']]
    assert len(rows) == 5  # Rail and four separately identified frame edges.
    assert sum(r['quantity'] for r in rows) == 17
    assert sum(r['quantity']==4 for r in rows) == 4
    assert result == before


@pytest.mark.parametrize('values', [MITRE_STAIR, dict(MITRE_STAIR, vertical_squares=2)])
def test_true_rail_mitre_shared_seams_all_four_bends(catalogue, seed_data, values):
    result = calculate('PANELLING_STAIR_HALF','plain',values,OPTIONS,catalogue,3)
    g = result['geometry']; plan = g['wall_layout']
    assert (g['slope_angle'], g['slope_mitre']) == (44.42,22.21)
    before = deepcopy(result)
    for name in ('Bottom','Top'):
        rails = [e for e in plan['elements'] if e['label'].startswith(name+' rail')]
        assert len(rails) == 3 and all(not e['provisional'] for e in rails)
        for left,right in zip(rails,rails[1:]):
            a,b = left['points'][1:3]
            assert a == pytest.approx(right['points'][0])
            assert b == pytest.approx(right['points'][-1])
            dx,dy = b[0]-a[0], b[1]-a[1]
            assert abs(dx)>1 and abs(dy)>1  # Solid angled seam, never a butt.
            assert math.degrees(math.atan(abs(dx/dy))) == pytest.approx(g['slope_mitre'],abs=.01)
            assert abs(dy) == pytest.approx(values['slat_width'])
        # Both slope boundaries retain the configured perpendicular width.
        slope = rails[1]['points']
        a,b = slope[:2]; p = slope[-1]
        distance = abs((b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])) / math.dist(a,b)
        assert distance == pytest.approx(values['slat_width'])
    parts = {label:p for p in plan['parts'] for label in p['labels']}
    assert parts['Top rail · Lower landing']['prepare_length_mm']==pytest.approx(1040.824829)
    assert parts['Top rail · Upper landing']['prepare_length_mm']==1000
    assert parts['Top rail · Lower landing']['installed_length_mm']==pytest.approx(1020.412415)
    assert any(e.get('profile_provisional') and e['kind']=='opening' for e in plan['elements'])
    assert all(not e['provisional'] for e in plan['elements'] if e['kind']=='opening')
    assert all(e['kind']!='bead' for e in plan['elements'])  # Plain stair has no unmodelled bead pieces.
    assert 'translate(4500 0) scale(-1 1)' in render_wall_plan(plan,'Stair','Left')
    assert calculate('PANELLING_STAIR_HALF','plain',values,dict(OPTIONS,high_end='Left'),catalogue,3)==result
    assert result==before
    summary = cut_summary(result['groups'])
    verticals = next(f for f in summary if f['label']=='Vertical')['rows']
    assert any(r['prepare_length_mm']==pytest.approx(817.97959) for r in verticals)
    assert not any(r['prepare_length_mm']==720 for r in verticals)
    # The baseline prepare demands, strip packing and prices are invariant to
    # geometry generation: consuming the summary cannot mutate these records.
    price = aggregate([result],catalogue,seed_data['pricing'])
    cut_summary(result['groups']); render_wall_plan(plan,'Stair')
    assert aggregate([result],catalogue,seed_data['pricing'])==price
    assert [c['length_mm'] for c in result['groups']['vertical']['cuts']]==pytest.approx([800,817.97959,817.97959,817.97959,800])


@pytest.mark.parametrize(('lower','upper'),[(0,0),(0,1000),(1000,0),(1,1)])
def test_mitre_rail_wall_end_clipping_and_missing_landings(catalogue,lower,upper):
    values = dict(MITRE_STAIR, lower_landing=lower, upper_landing=upper,
                  wall_length=2500+lower+upper)
    result=calculate('PANELLING_STAIR_HALF','plain',values,OPTIONS,catalogue,3)
    rails=[e for e in result['geometry']['wall_layout']['elements'] if ' rail · ' in e['label']]
    assert all(0<=x<=values['wall_length'] for rail in rails for x,y in rail['points'])


def test_current_quote_compact_summary_keeps_room_svgs_and_demand(app,signed_in):
    qid=create_quote(signed_in,app);rid=add_room(signed_in,app,qid,'Planning room')
    add_item(signed_in,app,qid,rid,'Stair','PANELLING_STAIR_HALF',MITRE_STAIR)
    add_item(signed_in,app,qid,rid,'Straight','PANELLING_HALF',HALF)
    with app.app_context():before=deepcopy(db.session.get(Quote,qid).result)
    for _ in range(2):
        page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
        assert 'Cut Summary' in page and '2 × 817.98mm' in page
        assert 'Finished cuts' not in page and '<summary>Workshop preparation' not in page
        assert 'Workshop Preparation' in page and 'stock-plan-svg' in page
        assert 'Wall Layout' in page and 'Room cut plan' in page
        assert 'Base cut 817.98' in page and 'Installed centreline 720' in page
    with app.app_context():assert db.session.get(Quote,qid).result==before
