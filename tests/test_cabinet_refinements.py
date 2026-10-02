from copy import deepcopy

import pytest

from app.calculations.cabinet import calculate_cabinet
from app.calculations.packing import CalculationError
from app.calculations.pricing import aggregate
from app.models import db, Material, PricingConfig, Quote, WorkItem, OwnedStock
from app.seed import seed
from app.services.quotes import material_plan
from test_application import create_quote, add_room, post_quote


def cabinet(catalogue, pricing, *, inputs=None, options=None, item_id='cabinet'):
    measurements = dict(unit_width=604, unit_height=704, unit_depth=400,
                        divider_count=0, shelves_per_bay=0, door_count=1,
                        workshop_hours=4, installation_days=1)
    measurements.update(inputs or {})
    choices = dict(cabinet_preset='custom', construction_mode='front',
                   carcass_material_id='mdf-18mm', door_banding='all', base_type='none')
    choices.update(options or {})
    return calculate_cabinet(measurements, choices, catalogue, pricing, item_id, 1)


def room(*items, room_id=1):
    return dict(id=room_id, name=f'Room {room_id}',
                items=[dict(id=index, name=f'Unit {index}', result=result)
                       for index, result in enumerate(items, 1)])


def test_new_catalogue_seeding_preserves_user_products_and_settings(app):
    with app.app_context():
        expected = [('mdf-18mm', 2440, 1220, 18, 29),
                    ('mdf-mr-18mm', 2440, 1220, 18, 46),
                    ('mdf-mr-9mm', 2440, 1220, 9, 35),
                    ('pse-100x25-2.4m', 2400, 100, 25, 7)]
        for identifier, length, width, thickness, price in expected:
            product = db.session.get(Material, identifier)
            assert (product.length_mm, product.width_mm, product.thickness_mm, product.price) == (length, width, thickness, price)
        product = db.session.get(Material, 'mdf-18mm')
        product.price = 39
        product.active = False
        db.session.delete(db.session.get(Material, 'mdf-mr-18mm'))
        db.session.add(Material(id='user-mr-sheet', category='mdf', profile='User profile',
            label='18mm MR MDF', length_mm=2440, width_mm=1220, thickness_mm=18,
            price=51, active=True, uses=[]))
        config = db.session.get(PricingConfig, 1)
        config.values = dict(config.values, cabinet_shaker_stile_width=110)
        db.session.commit()
        count = db.session.query(Material).count()
        seed(); seed()
        assert db.session.query(Material).count() == count
        assert db.session.get(Material, 'mdf-mr-18mm') is None
        assert db.session.get(Material, 'user-mr-sheet').price == 51
        assert product.price == 39 and not product.active
        assert db.session.get(PricingConfig, 1).values['cabinet_shaker_stile_width'] == 110


@pytest.mark.parametrize('preset', ['window_seat', 'bench', 'custom'])
def test_top_opening_geometry_and_automatic_divider_size(catalogue, seed_data, preset):
    result = cabinet(catalogue, seed_data['pricing'], inputs=dict(unit_width=2000,
        unit_height=500, unit_depth=500, divider_count=2, divider_height=999,
        door_count=3), options=dict(cabinet_preset=preset, construction_mode='top',
        back_enabled=True, face_frame=True, worktop=True, hinged_lid=True))
    parts = {p['label']: p for p in result['sheet_parts']}
    assert (parts['Bottom']['cut_length_mm'], parts['Bottom']['cut_width_mm']) == (2000, 500)
    for label in ('Front panel', 'Back panel'):
        assert (parts[label]['cut_length_mm'], parts[label]['cut_width_mm']) == (2000, 482)
    for label in ('Left side', 'Right side', 'Divider 1', 'Divider 2'):
        assert (parts[label]['cut_length_mm'], parts[label]['cut_width_mm']) == (482, 464)
    assert (parts['Full top / lid']['cut_length_mm'], parts['Full top / lid']['cut_width_mm']) == (2000, 500)
    assert parts['Full top / lid']['notes'] == 'Hinged lid'
    assert result['geometry']['bay_width'] == pytest.approx((1964 - 36) / 3)
    assert not any(p['component'] in ('door', 'face_frame', 'worktop', 'top_rail') for p in parts.values())


@pytest.mark.parametrize(('base', 'base_inputs'), [
    ('legs', dict(feet_height=100)),
    ('plinth', dict(plinth_height=100, plinth_front_recess=50,
                   plinth_front_back_length=1900, plinth_side_length=400))])
def test_bench_left_scribe_covers_lid_and_base(catalogue, seed_data, base, base_inputs):
    result = cabinet(catalogue, seed_data['pricing'], inputs=dict(unit_width=2000,
        unit_height=482, unit_depth=500, door_count=0, **base_inputs),
        options=dict(cabinet_preset='bench', scribed_sides='left', base_type=base))
    parts = {p['label']: p for p in result['sheet_parts']}
    assert result['geometry']['assembly_height'] == 600
    left = parts['Left end scribe']
    assert (left['cut_length_mm'], left['cut_width_mm']) == (650, 550)
    assert (left['finished_length_mm'], left['finished_width_mm']) == (600, 500)
    assert 'Right end scribe' not in parts
    assert result['geometry']['unit_height'] == 482


@pytest.mark.parametrize('banding', ['none', 'all'])
def test_shaker_frame_panel_and_bead_preserve_finished_envelope(catalogue, seed_data, banding):
    result = cabinet(catalogue, seed_data['pricing'], options=dict(door_style='shaker',
        door_banding=banding, shaker_panel_material_id='mdf-mr-9mm',
        door_bead_id='bead-glass_bead-9x9'))
    parts = {p['label']: p for p in result['sheet_parts']}
    stile, rail, panel = [parts[label] for label in (
        'Door 1 stile', 'Door 1 rail', 'Door 1 Shaker centre panel')]
    band = 1 if banding == 'all' else 0
    assert (stile['finished_length_mm'], stile['finished_width_mm'], stile['quantity']) == (700, 100, 2)
    assert (stile['cut_length_mm'], stile['cut_width_mm']) == (700 - 2 * band, 100 - band)
    assert (rail['cut_length_mm'], rail['cut_width_mm'], rail['quantity']) == (400, 100 - band, 2)
    assert 2 * stile['cut_width_mm'] + rail['cut_length_mm'] + 2 * band == 600
    assert stile['cut_length_mm'] + 2 * band == 700
    assert (panel['cut_length_mm'], panel['cut_width_mm'], panel['thickness_mm']) == (410, 510, 9)
    assert panel['material_id'] == 'mdf-mr-9mm'
    door = result['geometry']['doors'][0]
    assert (door['opening_width_mm'], door['opening_height_mm']) == (400, 500)
    cuts = next(iter(result['groups'].values()))['cuts']
    assert sorted(c['length_mm'] for c in cuts) == [400, 400, 500, 500]
    assert all(c['label'].startswith('Door 1 bead ') for c in cuts)


def test_flat_bead_custom_front_and_configured_dimensions(catalogue, seed_data):
    pricing = dict(seed_data['pricing'], cabinet_flat_bead_inset=80)
    default = cabinet(catalogue, seed_data['pricing'], options=dict(door_bead_id='bead-glass_bead-9x9'))
    assert sorted(c['length_mm'] for g in default['groups'].values() for c in g['cuts']) == [400, 400, 500, 500]
    adjusted = cabinet(catalogue, pricing, inputs=dict(door_bead_inset=90), options=dict(door_bead_id='bead-glass_bead-9x9'))
    assert sorted(c['length_mm'] for g in adjusted['groups'].values() for c in g['cuts']) == [420, 420, 520, 520]
    parts = {p['label']: p for p in default['sheet_parts']}
    assert parts['Bottom']['cut_length_mm'] == 568
    assert parts['Left side']['cut_length_mm'] == 704
    assert parts['Door 1']['cut_width_mm'] == 598
    assert parts['Door 1']['cut_length_mm'] == 698


def test_pse_worktop_ripped_strip_room_packing_and_charges(catalogue, seed_data):
    options = dict(worktop_type='pse', pse_material_id='pse-100x25-2.4m',
                   door_style='shaker', door_bead_id='bead-glass_bead-9x9')
    result = cabinet(catalogue, seed_data['pricing'], inputs=dict(opening_width=1000), options=options)
    timber = result['groups']['worktop_pse-100x25-2.4m']['cuts']
    assert [c['width_mm'] for c in timber] == [100, 100, 100, 100, 50]
    assert all(c['length_mm'] == 1100 and c['no_join'] for c in timber)
    bench = cabinet(catalogue, seed_data['pricing'], inputs=dict(unit_width=500,
        unit_height=300, unit_depth=300, door_count=0), options=dict(cabinet_preset='bench'), item_id='bench')
    together = aggregate([result, bench], catalogue, seed_data['pricing'], rooms=[room(result, bench)])
    pse = [s for s in together['room_stocks'] if s['category'] == 'pse']
    assert len(pse) == 3
    assert sorted(len(s['cuts']) for s in pse) == [1, 2, 2]
    assert {c['label'] for s in pse for c in s['cuts']} == {f'Worktop strip {i}' for i in range(1, 6)}
    material = next(r for r in together['materials'] if r['category'] == 'pse')
    assert material['cost'] == 21
    assert together['stock_material_cost'] == sum(catalogue[s['material_id']]['price'] for s in together['room_stocks'])
    assert together['labour_cost'] == 540
    assert together['mastic_units'] == 0
    assert any(s.get('packing_kind') == 'sheet' and len({c['wall_name'] for c in s['cuts']}) > 1 for s in together['room_stocks'])
    separate = aggregate([result, deepcopy(result)], catalogue, seed_data['pricing'],
        rooms=[room(result), room(deepcopy(result), room_id=2)])
    assert len([s for s in separate['room_stocks'] if s['category'] == 'pse']) == 6
    with pytest.raises(CalculationError, match='cannot be joined automatically'):
        cabinet(catalogue, seed_data['pricing'], inputs=dict(opening_width=2400), options=options)


def test_refined_quote_save_reopen_pse_extras_purchase_and_reservation(app, signed_in):
    qid = create_quote(signed_in, app)
    rid = add_room(signed_in, app, qid, 'Cabinet room')
    assert post_quote(signed_in, app, qid, 'add_item', room_id=rid, name='Shaker unit', type='CABINET').status_code == 302
    with app.app_context():
        item_id = db.session.scalar(db.select(WorkItem.id).where(WorkItem.room_id == rid))
    response = post_quote(signed_in, app, qid, 'edit_item', room_id=rid, item_id=item_id,
        name='Shaker unit', type='CABINET', subtype='plain', position=0,
        cabinet_preset='alcove', construction_mode='front', opening_width=1000,
        unit_width=900, unit_height=700, unit_depth=400, divider_count=0,
        shelves_per_bay=0, door_count=2, carcass_material_id='mdf-mr-18mm',
        top_rails='on', face_frame='on', back_enabled='on', back_material_id='mdf-mr-9mm',
        door_style='shaker', shaker_panel_material_id='mdf-mr-9mm', door_banding='all',
        door_bead_id='bead-glass_bead-9x9', worktop_type='pse', pse_material_id='pse-100x25-2.4m',
        front_overhang=0, base_type='none', workshop_hours=4, installation_days=1)
    assert response.status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        assert quote.result['valid']
        item = db.session.get(WorkItem, item_id)
        assert item.options['door_style'] == 'shaker' and item.options['worktop_type'] == 'pse'
        assert item.result['geometry']['doors'][0]['style'] == 'shaker'
        pse_row = next(r for r in material_plan(quote) if r['category'] == 'pse')
        assert pse_row['calculated_quantity'] == 3 and pse_row['chargeable_cost'] == 21
        assert quote.result['labour_cost'] == 270 and quote.result['mastic_units'] == 0
        before_charge = quote.result['chargeable_material_cost']
        stock = OwnedStock(material_id='pse-100x25-2.4m', stock_type='offcut', usable_length_mm=2250, quantity=1)
        db.session.add(stock); db.session.commit(); stock_id = stock.id
    html = signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert 'Door 1 Shaker centre panel' in html and 'Worktop strip 5' in html
    assert 'sheet-diagram' in html and 'Glue-up PSE timber' in html and 'Free-standing Bench' in html
    assert 'Cut Summary' in html and 'Pse Cut Plan' in html
    assert post_quote(signed_in, app, qid, 'allocate_owned_stock', room_id=rid,
        material_id='pse-100x25-2.4m', owned_stock_id=stock_id, quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        pse_row = next(r for r in material_plan(quote) if r['category'] == 'pse')
        assert pse_row['need_to_purchase_quantity'] == 2
        assert quote.result['chargeable_material_cost'] == before_charge
    assert post_quote(signed_in, app, qid, 'set_extra_material', room_id=rid,
        material_id='pse-100x25-2.4m', extra_quantity=1).status_code == 302
    assert post_quote(signed_in, app, qid, 'mark_material_purchased', room_id=rid,
        material_id='pse-100x25-2.4m', quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        pse_row = next(r for r in material_plan(quote) if r['category'] == 'pse')
        assert pse_row['extra_quantity'] == 1 and pse_row['room_id'] == rid
        assert pse_row['need_to_purchase_quantity'] == 2
        assert quote.result['chargeable_material_cost'] == before_charge + 7
        quote.status = 'Accepted'; db.session.commit()
    assert '100 × 25mm PSE timber' in signed_in.get('/').get_data(as_text=True)
    assert signed_in.get('/materials').status_code == 200
