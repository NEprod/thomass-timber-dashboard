from copy import deepcopy
import math
import re
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


def assert_uniform_svg_scale(root):
    # The viewBox maps into any constrained viewport using one 'meet' scale;
    # the only axis transforms allowed are equal-magnitude orientation flips.
    assert root.attrib['preserveAspectRatio'] == 'xMidYMid meet'
    for node in root.iter():
        for values in re.findall(r'scale\(([^)]+)\)', node.attrib.get('transform', '')):
            factors = [float(v) for v in values.replace(',', ' ').split()]
            assert len(factors) == 1 or abs(factors[0]) == abs(factors[1])


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
    root = ET.fromstring(svg)
    assert_uniform_svg_scale(root)
    wall = next(node for node in root.iter() if node.attrib.get('data-kind') == 'wall')
    points = [tuple(map(float, p.split(','))) for p in wall.attrib['points'].split()]
    assert points[1][0] - points[0][0] == inputs['wall_length']
    assert points[2][1] - points[1][1] == inputs['height']
    assert '<script>' not in svg and '&lt;script&gt;' in svg
    assert 'Wall 3000 mm' in svg and 'Opening 625 mm' in svg
    assert '<title>' in svg and '<desc>' in svg and 'role="img"' in svg


@pytest.mark.parametrize('high_end', ['Right', 'Left'])
def test_rendered_stair_preserves_4000_slope_2500_run_proportions(catalogue, high_end):
    inputs = dict(STAIR, wall_length=3000, slope_length=4000)
    result = calculate('PANELLING_STAIR_HALF', 'plain', inputs, OPTIONS, catalogue, 3)
    assert result['geometry']['horizontal_run'] == 2500
    assert result['geometry']['slope_angle'] == 51.32
    plan = layout(result)
    before = deepcopy(plan)
    root = ET.fromstring(render_wall_plan(plan, 'Proportion regression', high_end))
    assert plan == before
    assert_uniform_svg_scale(root)
    wall = next(node for node in root.iter() if node.attrib.get('data-kind') == 'wall')
    points = [tuple(map(float, p.split(','))) for p in wall.attrib['points'].split()]
    run = points[2][0] - points[1][0]
    rise = points[2][1] - points[1][1]
    expected_rise = math.sqrt(4000 ** 2 - 2500 ** 2)
    assert run == 2500
    assert rise == pytest.approx(expected_rise, abs=0.01)
    assert rise / run == pytest.approx(expected_rise / 2500, rel=1e-6)
    assert math.degrees(math.atan2(rise, run)) == pytest.approx(51.32, abs=0.01)
    # Include height-limited desktop and width-limited narrow viewports. SVG meet
    # scales both coordinate axes together even when CSS caps the display height.
    _, _, view_width, view_height = map(float, root.attrib['viewBox'].split())
    for available_width, available_height in [(1200, 720), (800, 720), (390, 844)]:
        scale = min(available_width / view_width, available_height / view_height)
        assert (rise * scale) / (run * scale) == pytest.approx(expected_rise / 2500, rel=1e-6)


REPRESENTATIVE_STAIR = dict(STAIR, wall_length=4500, lower_landing=1000,
                            upper_landing=1000, slope_length=4000)


def boundary_y(boundary, x):
    for (a, ya), (b, yb) in zip(boundary, boundary[1:]):
        if a <= x <= b and b > a:
            return ya + (yb - ya) * (x - a) / (b - a)
    raise AssertionError(f'No rail boundary at {x}')


@pytest.mark.parametrize('values', [STAIR, REPRESENTATIVE_STAIR,
                                   dict(STAIR, lower_landing=400, upper_landing=400),
                                   dict(STAIR, lower_landing=0, upper_landing=0, slope_length=2000),
                                   dict(REPRESENTATIVE_STAIR, vertical_squares=2)])
def test_installed_stair_envelope_true_rail_width_and_batten_intersections(catalogue, values):
    result = calculate('PANELLING_STAIR_HALF', 'plain', values, OPTIONS, catalogue, 3)
    plan = layout(result)
    boundaries = plan['boundaries']
    assert plan['installed_panel_height_mm'] == values['height']
    assert plan['height_mm'] == pytest.approx(math.sqrt(values['slope_length'] ** 2 - result['geometry']['horizontal_run'] ** 2) + values['height'])
    for x in (0, values['lower_landing'], values['wall_length'] - values['upper_landing'], values['wall_length']):
        assert boundary_y(boundaries['top_outer'], x) - boundary_y(boundaries['bottom_outer'], x) == pytest.approx(values['height'])
    for name in ('Top', 'Bottom'):
        rails = [e for e in plan['elements'] if e['kind'] == 'mdf' and e['label'].startswith(name + ' rail')]
        for left, right in zip(rails, rails[1:]):
            half = len(left['points']) // 2
            assert left['points'][half - 1] == pytest.approx(right['points'][0])
            assert left['points'][half] == pytest.approx(right['points'][-1])
    cosine = result['geometry']['horizontal_run'] / values['slope_length']
    x = values['lower_landing'] + result['geometry']['horizontal_run'] / 2
    assert (boundary_y(boundaries['bottom_inner'], x) - boundary_y(boundaries['bottom_outer'], x)) * cosine == pytest.approx(values['slat_width'])
    assert (boundary_y(boundaries['top_outer'], x) - boundary_y(boundaries['top_inner'], x)) * cosine == pytest.approx(values['slat_width'])
    for element in plan['elements']:
        if element['kind'] == 'mdf' and element['label'].startswith('Vertical batten'):
            half = len(element['points']) // 2
            for x, y in element['points'][:half]:
                assert y == pytest.approx(boundary_y(boundaries['bottom_inner'], x))
            for x, y in element['points'][half:]:
                assert y == pytest.approx(boundary_y(boundaries['top_inner'], x))
            # Both ends of each batten side share x: it remains vertical.
            assert element['points'][0][0] == element['points'][-1][0]
            assert element['points'][half - 1][0] == element['points'][half][0]


def test_installed_prepare_grouped_parts_transitions_and_landing_allowances(catalogue, seed_data):
    result = calculate('PANELLING_STAIR_HALF', 'bead', REPRESENTATIVE_STAIR,
                       dict(OPTIONS, bead_id='bead-glass_bead-9x9'), catalogue, 3)
    plan = layout(result)
    verticals = [p for p in plan['parts'] if p['component'] == 'Vertical batten']
    angled = next(p for p in verticals if p['installed_length_mm'] == 680)
    assert angled['quantity'] == 3 and angled['prepare_length_mm'] == pytest.approx(804.89996)
    assert not angled['trim_to_fit'] and not angled['provisional']
    assert all(p['prepare_length_mm'] >= p['installed_length_mm'] for p in verticals if not p['provisional'])
    assert [c['length_mm'] for c in result['groups']['vertical']['cuts']] == pytest.approx([800,804.89996,804.89996,804.89996,800])
    parts = {label: p for p in plan['parts'] for label in p['labels']}
    assert (parts['Top rail · Lower landing']['installed_length_mm'], parts['Top rail · Lower landing']['prepare_length_mm']) == pytest.approx((1024.019223,1048.038446))
    assert (parts['Top rail · Upper landing']['installed_length_mm'], parts['Top rail · Upper landing']['prepare_length_mm']) == pytest.approx((975.980777,1000))
    assert parts['Bottom rail · Lower landing']['prepare_length_mm'] == 1000
    assert parts['Bottom rail · Upper landing']['prepare_length_mm'] == pytest.approx(1048.038446)
    slope = parts['Top rail · Slope']
    assert slope['quantity'] == 2 and slope['installed_length_mm'] == pytest.approx(4000)
    assert slope['prepare_length_mm'] == pytest.approx(4048.038446)
    assert len(slope['cut_ids']) == 4  # Exact 2440 + 1608.038446 joined demands per rail.
    openings = [p for p in plan['parts'] if p['component'] == 'Panel opening']
    exact = next(p for p in openings if p['installed_dimensions']['height_mm'] == 680)
    assert exact['installed_dimensions'] == dict(width_mm=1000, height_mm=680)
    assert exact['prepare_dimensions'] is None
    assert result['geometry']['square_width'] == 1000 and result['geometry']['square_height'] == 800
    assert not any(p['provisional'] or p['trim_to_fit'] for p in plan['parts'])
    svg = render_wall_plan(plan, 'Installed wall')
    assert 'Installed height 1000 mm' in svg and 'Trim to fit' not in svg and 'stroke-dasharray' not in svg
    # Orientation is renderer-only: both canonical paths, stock and price match.
    left = calculate('PANELLING_STAIR_HALF', 'bead', REPRESENTATIVE_STAIR,
                     dict(OPTIONS, bead_id='bead-glass_bead-9x9', high_end='Left'), catalogue, 3)
    assert left == result
    assert aggregate([left], catalogue, seed_data['pricing']) == aggregate([result], catalogue, seed_data['pricing'])
    assert 'translate(4500 0) scale(-1 1)' in render_wall_plan(plan, 'Installed wall', 'Left')


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
        if kind=='PANELLING_STAIR_HALF':
            openings=[e for e in layout(right)['elements'] if e['kind']=='opening']
            assert all(not e['provisional'] for e in openings)
            assert sum(e['profile_provisional'] for e in openings)==2
        else:
            provisional = [e for e in layout(right)['elements'] if e['provisional'] and e['kind']=='frame']
            assert not provisional
            assert len([e for e in layout(right)['elements'] if e['kind']=='frame'])==20
        assert not any('transition' in d['label'].lower() for d in layout(right)['dimensions'])
    svg = render_wall_plan(layout(right), 'Stair wall')
    mirrored = render_wall_plan(layout(left), 'Stair wall', 'Left')
    assert 'translate(1500 0) scale(-1 1)' not in svg
    assert 'translate(1500 0) scale(-1 1)' in mirrored
    assert 'high end right' in svg and 'high end left' in mirrored
    if kind=='DADO_STAIR' and style != 'Dado':
        assert 'stroke-dasharray' not in svg and 'Trim to fit' not in svg


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
    assert all(c['requirement_status']=='EXACT' for c in first)
    assert all('stock_allowance' not in c['angle_information'] for c in first)
    assert (result['horizontal_strips'],result['vertical_strips']) == (2,2)


def test_current_quote_renders_and_reopens_installed_prepare_parts(app, signed_in):
    qid = create_quote(signed_in, app)
    rid = add_room(signed_in, app, qid, 'Installed stair room')
    iid = add_item(signed_in, app, qid, rid, 'Installed stair', 'PANELLING_STAIR_HALF', REPRESENTATIVE_STAIR)
    for _ in range(2):
        page = signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
        assert 'Installed Dimensions' in page
        assert '3 × Vertical batten' in page and 'Installed centreline: 680.00 mm' in page and 'Base cut: 804.90 mm' in page
        assert 'Installed height 1000 mm' in page and 'Installed vertical sides' in page
    with app.app_context():
        parts = db.session.get(WorkItem, iid).result['geometry']['wall_layout']['parts']
        assert next(p for p in parts if p['installed_length_mm'] == 680)['prepare_length_mm'] == pytest.approx(804.89996)
