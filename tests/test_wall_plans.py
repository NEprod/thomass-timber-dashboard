from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest

from app.calculations.sections import calculate
from app.calculations.pricing import aggregate
from app.models import db, Quote, WorkItem
from app.services.wall_plans import render_wall_plan
from test_application import create_quote, add_room, add_item, post_quote
from test_calculations import FULL, HALF, STAIR, OPTIONS


def layout(result):
    return result['geometry']['wall_layout']


@pytest.mark.parametrize(('kind', 'inputs', 'members', 'openings'), [
    ('PANELLING_FULL', FULL, 17, 8),
    ('PANELLING_HALF', dict(HALF, vertical_squares=2), 11, 8)])
def test_straight_panelling_geometry_counts_dimensions_and_safe_svg(catalogue, kind, inputs, members, openings):
    result = calculate(kind, 'bead', inputs, dict(OPTIONS, bead_id='bead-glass_bead-9x9'), catalogue, 3)
    plan = layout(result)
    assert (plan['width_mm'], plan['height_mm']) == (inputs['wall_length'], inputs['height'])
    assert sum(e['kind'] == 'mdf' for e in plan['elements']) == members
    assert sum(e['kind'] == 'opening' for e in plan['elements']) == openings
    assert sum(e['kind'] == 'bead' for e in plan['elements']) == openings
    first = next(e for e in plan['elements'] if e['kind'] == 'opening')
    assert first['points'][0] == [100, 100]
    assert first['points'][1][0] - first['points'][0][0] == result['geometry']['square_width']
    assert plan == layout(calculate(kind, 'bead', inputs, dict(OPTIONS, bead_id='bead-glass_bead-9x9'), catalogue, 3))
    svg = render_wall_plan(plan, '<script>alert("unsafe")</script> & Wall')
    ET.fromstring(svg)
    assert '<script>' not in svg and '&lt;script&gt;' in svg
    assert 'Wall 3000 mm' in svg and 'Opening 625 mm' in svg
    assert '<title>' in svg and '<desc>' in svg and 'role="img"' in svg


def dado(catalogue, style='Dado', **values):
    inputs = dict(wall_length=3000, gap_width=100, bottom_squares=4, bottom_zone_height=1000)
    inputs.update(values)
    return calculate('DADO_STRAIGHT', style, inputs,
        dict(dado_rail_id='dado-45mm-3m', dado_square_id='dado-45mm-3m'), catalogue, 3)


def test_plain_dado_explicit_height_and_missing_height_do_not_change_material(catalogue, seed_data):
    missing, given = dado(catalogue), dado(catalogue, dado_height=1100)
    assert layout(missing) is None
    assert missing['groups'] == given['groups']
    assert aggregate([missing], catalogue, seed_data['pricing']) == aggregate([given], catalogue, seed_data['pricing'])
    plan = layout(given)
    rail = next(e for e in plan['elements'] if e['kind'] == 'dado')
    assert rail['points'] == [[0, 1100], [3000, 1100]]
    assert not any(e['kind'] in ('opening', 'frame', 'mdf') for e in plan['elements'])
    svg = render_wall_plan(plan, 'Plain rail')
    assert 'Centreline 1100 mm' in svg and 'Finished floor to dado centreline 1100 mm' in svg


def test_dado_squares_reuses_clear_zone_height_not_plain_height(catalogue):
    result = dado(catalogue, 'Dado Squares Bottom', dado_height=9999)
    plan = layout(result)
    assert result['geometry']['layout_height_mm'] == 1000
    assert next(e for e in plan['elements'] if e['kind'] == 'dado')['points'] == [[0, 1000], [3000, 1000]]
    frames = [e for e in plan['elements'] if e['kind'] == 'frame']
    assert len(frames) == len(result['geometry']['frames']) == 4
    assert frames[0]['points'] == [[100, 100], [725, 100], [725, 900], [100, 900]]
    assert 'Clear zone 1000 mm' in render_wall_plan(plan, 'Bottom squares')


@pytest.mark.parametrize(('kind','style'), [('PANELLING_STAIR_HALF','plain'), ('DADO_STAIR','Dado'), ('DADO_STAIR','Dado Squares Bottom')])
def test_stair_mirror_golden_values_and_provisional_regions(catalogue, seed_data, kind, style):
    inputs = dict(STAIR, dado_height=1000, gap_width=100, bottom_squares=4, bottom_zone_height=1000)
    options = dict(OPTIONS, dado_rail_id='dado-45mm-3m', dado_square_id='dado-45mm-3m')
    right = calculate(kind, style, inputs, dict(options, high_end='Right'), catalogue, 3)
    left = calculate(kind, style, inputs, dict(options, high_end='Left'), catalogue, 3)
    assert right == left
    assert aggregate([right], catalogue, seed_data['pricing']) == aggregate([left], catalogue, seed_data['pricing'])
    g = right['geometry']
    assert g['horizontal_run'] == 1000 and g['slope_angle'] == 33.56 and g['slope_mitre'] == 16.78
    assert g['acute_included_angle'] == 56.44 and g['obtuse_included_angle'] == 123.56
    assert g['top_angle_setting'] == 61.78 and g['bottom_angle_setting'] == 28.22
    if style != 'Dado':
        assert (g['square_width'],g['square_height'],g['angled_square_width'],g['angled_square_height']) == (250,800,300,960)
        provisional = [e for e in layout(right)['elements'] if e['provisional'] and e['kind'] in ('opening','frame')]
        assert len(provisional) == 2
        assert all(e['label'] == 'Trim to fit on site' for e in provisional)
        assert not any('transition' in d['label'].lower() for d in layout(right)['dimensions'])
    svg = render_wall_plan(layout(right), 'Stair wall')
    mirrored = render_wall_plan(layout(left), 'Stair wall', 'Left')
    assert 'translate(1500 0) scale(-1 1)' not in svg
    assert 'translate(1500 0) scale(-1 1)' in mirrored
    assert 'high end right' in svg and 'high end left' in mirrored
    if style != 'Dado':
        assert 'stroke-dasharray="6 4"' in svg and 'Trim to fit on site' in svg


def test_current_quote_orientation_height_reopen_recalc_and_unsupported(app, signed_in):
    qid = create_quote(signed_in, app)
    rid = add_room(signed_in, app, qid, 'Layout room')
    iid = add_item(signed_in, app, qid, rid, 'Stair wall', 'PANELLING_STAIR_HALF', STAIR)
    with app.app_context():
        item = db.session.get(WorkItem, iid)
        assert item.options['high_end'] == 'Right'
        before = deepcopy(item.result)
        totals = deepcopy(db.session.get(Quote, qid).result)
        # Current-schema record without the new option: the display defaults right.
        item.options = {k:v for k,v in item.options.items() if k != 'high_end'}
        db.session.commit()
    page = signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert 'high end right' in page
    assert post_quote(signed_in, app, qid, 'edit_item', room_id=rid, item_id=iid,
        name='Stair wall', type='PANELLING_STAIR_HALF', subtype='plain', position=0,
        mdf_id='mdf-9mm', high_end='Left', **STAIR).status_code == 302
    with app.app_context():
        assert db.session.get(WorkItem, iid).result == before
        assert db.session.get(Quote, qid).result == totals
    assert 'translate(1500 0) scale(-1 1)' in signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    for height in ('', '1200'):
        assert post_quote(signed_in, app, qid, 'edit_item', room_id=rid, item_id=iid,
            name='Dado wall', type='DADO_STRAIGHT', subtype='Dado', position=0,
            dado_rail_id='dado-45mm-3m', wall_length=3000, dado_height=height).status_code == 302
        page = signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
        assert ('Installation height is not yet set' if not height else 'Centreline 1200 mm') in page
    with app.app_context():
        assert db.session.get(WorkItem, iid).inputs['dado_height'] == '1200'
    assert post_quote(signed_in, app, qid, 'edit_item', room_id=rid, item_id=iid,
        name='Half wall', type='PANELLING_HALF', subtype='plain', position=0,
        mdf_id='mdf-9mm', **dict(HALF, wall_length=3500, horizontal_squares=5)).status_code == 302
    page = signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert 'Wall 3500 mm' in page and '5 × 1 openings' in page
    assert 'Centreline 1200 mm' not in page
    # Unsupported current work type has its normal result, never an empty wall SVG.
    assert post_quote(signed_in, app, qid, 'edit_item', room_id=rid, item_id=iid,
        name='Coving', type='COVING', subtype='plain', position=0,
        wall_length=2400, start_corner='Internal', end_corner='External').status_code == 302
    page = signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert 'Finished Coving cut' in page and 'wall-plan-svg' not in page


def test_stair_transition_bead_allowances_remain_golden(catalogue):
    result = calculate('PANELLING_STAIR_HALF', 'bead', STAIR,
        dict(OPTIONS, bead_id='bead-glass_bead-9x9'), catalogue, 3)
    cuts = result['groups']['stair_opening_beads']['cuts']
    first = [c for c in cuts if c['angle_information']['square'] == 1]
    assert sorted(c['length_mm'] for c in first) == [120,120,180,180,960,960]
    assert all(c['angle_information']['stock_allowance'] for c in first)
    assert (result['horizontal_strips'],result['vertical_strips']) == (2,3)
