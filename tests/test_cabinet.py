from copy import deepcopy

import pytest

from app.calculations.cabinet import calculate_cabinet
from app.calculations.sections import calculate
from app.calculations.packing import CalculationError
from app.calculations.pricing import aggregate
from app.calculations.sheet_optimizer import pack_sheet_parts, parts_on_owned_sheet, _plan
from app.models import db, Quote, Room, WorkItem, Material, Customer, OwnedStock, OwnedStockAllocation
from app.services.quotes import current_snapshot, reaggregate, material_plan
from test_application import create_quote, add_room, post_quote


def _parts(*sizes, rotation=True):
    return [dict(id=str(index), label=f'Part {index}', cut_length_mm=length,
                 cut_width_mm=width, rotation_allowed=rotation)
            for index, (length, width) in enumerate(sizes, 1)]


def _valid_tree(node):
    if node['kind'] != 'split':
        return [node]
    first, second = node['first'], node['second']
    if node['axis'] == 'vertical':
        assert first['y'] == second['y'] == node['y']
        assert first['width_mm'] == second['width_mm'] == node['width_mm']
        assert first['x'] + first['length_mm'] + node['kerf_mm'] == second['x']
        assert first['length_mm'] + second['length_mm'] + node['kerf_mm'] == node['length_mm']
    else:
        assert first['x'] == second['x'] == node['x']
        assert first['length_mm'] == second['length_mm'] == node['length_mm']
        assert first['y'] + first['width_mm'] + node['kerf_mm'] == second['y']
        assert first['width_mm'] + second['width_mm'] + node['kerf_mm'] == node['width_mm']
    return _valid_tree(first) + _valid_tree(second)


def test_sheet_optimiser_guillotine_trim_kerf_rotation_and_determinism():
    parts = _parts((800, 450), (800, 450), (964, 450), (964, 100))
    sheets = pack_sheet_parts(parts, 2440, 1220, trim=10, kerf=3)
    assert len(sheets) == 1
    assert sheets == pack_sheet_parts(parts, 2440, 1220, trim=10, kerf=3)
    assert {p['id'] for p in sheets[0]['placements']} == {'1', '2', '3', '4'}
    leaves = _valid_tree(sheets[0]['tree'])
    assert sum(node['kind'] == 'part' for node in leaves) == 4
    assert sheets[0]['tree']['x'] == 10
    assert sheets[0]['tree']['length_mm'] == 2420
    assert sheets[0]['tree']['width_mm'] == 1200
    assert len(pack_sheet_parts(_parts((1800, 800), (600, 800)), 2440, 1220, trim=10, kerf=3)) == 1
    with pytest.raises(CalculationError, match='exceeds available sheet'):
        pack_sheet_parts(_parts((2430, 100)), 2440, 1220, trim=10)
    with pytest.raises(CalculationError, match='exceeds available sheet'):
        pack_sheet_parts(_parts((1210, 1000), rotation=False), 1220, 2440, trim=10)
    rotated = pack_sheet_parts(_parts((1210, 1000)), 1220, 2440, trim=10)
    assert rotated[0]['placements'][0]['rotated']
    assert len(pack_sheet_parts(_parts((600, 600), (600, 600)), 1220, 600, trim=0, kerf=10)) == 1
    assert len(pack_sheet_parts(_parts((600, 600), (600, 600)), 1220, 600, trim=0, kerf=30)) == 2


def test_owned_sheet_subset_is_guillotine_cuttable():
    placed, remaining = parts_on_owned_sheet(_parts((800, 450), (800, 450), (800, 450)),
                                             900, 500, kerf=3)
    assert len(placed) == 1 and len(remaining) == 2


def test_sheet_optimiser_improves_on_naive_order():
    parts = _parts((650, 300), (650, 150), (650, 250),
                   (550, 400), (400, 250), (550, 250))
    naive, _ = _plan(parts, 1000, 600, 0, 3, parts, True)
    better = pack_sheet_parts(parts, 1000, 600, trim=0, kerf=3)
    assert len(naive) == 3
    assert len(better) == 2
    assert all(sum(node['kind'] == 'part' for node in _valid_tree(sheet['tree'])) > 0
               for sheet in better)


def _cabinet_catalogue(catalogue):
    catalogue = deepcopy(catalogue)
    catalogue['mdf-18mm'] = dict(catalogue['mdf-12mm'], id='mdf-18mm', profile='18mm',
                                  label='18mm MDF sheet', thickness_mm=18, price=30)
    return catalogue


def _cabinet_options(**other):
    return dict(cabinet_preset='alcove', carcass_material_id='mdf-18mm',
                back_material_id='mdf-9mm', face_frame=True, top_rails=True,
                worktop=True, door_banding='all', base_type='none', **other)


def test_alcove_parts_back_face_frame_bays_doors_and_labour(catalogue, seed_data):
    catalogue = _cabinet_catalogue(catalogue)
    inputs = dict(opening_width=1800, unit_width=1600, unit_height=800, unit_depth=450,
                  divider_count=1, divider_height=782, shelves_per_bay=1, door_count=2,
                  front_overhang=20, workshop_hours=4, installation_days=1)
    result = calculate_cabinet(inputs, _cabinet_options(back_enabled=True), catalogue,
                               seed_data['pricing'], 'cab-1', 7)
    by_label = {part['label']: part for part in result['sheet_parts']}
    assert by_label['Left side']['cut_length_mm'] == 800
    assert by_label['Bottom']['cut_length_mm'] == 1564
    assert by_label['Front top rail']['cut_width_mm'] == 100
    assert by_label['Rear top rail']['cut_length_mm'] == 1564
    assert result['geometry']['bay_width'] == 773
    assert by_label['Bay 1 shelf 1']['cut_length_mm'] == 773
    assert by_label['Bay 2 shelf 1']['cut_width_mm'] == 382
    without_back = calculate_cabinet(inputs, _cabinet_options(back_enabled=False),
                                     catalogue, seed_data['pricing'], 'cab-no-back')
    assert without_back['geometry']['shelf_depth'] == 432
    assert by_label['Inset back']['cut_length_mm'] == 1574
    assert by_label['Inset back']['cut_width_mm'] == 764
    assert result['geometry']['back_position'] == dict(front_face_from_rear_mm=50,
                                                        rear_face_from_rear_mm=41)
    assert by_label['Left side stile / scribe']['cut_width_mm'] == 150
    assert by_label['Left side stile / scribe']['cut_length_mm'] == 900
    assert by_label['Left side stile / scribe']['quantity'] == 2
    assert by_label['Right side stile / scribe']['quantity'] == 2
    assert by_label['Bottom face-frame rail']['cut_length_mm'] == 1600
    assert by_label['Bottom face-frame rail']['quantity'] == 2
    assert by_label['Worktop cut blank']['cut_length_mm'] == 1900
    assert by_label['Worktop cut blank']['cut_width_mm'] == 520
    assert by_label['Door 1']['finished_width_mm'] == 797
    assert by_label['Door 1']['finished_length_mm'] == 796
    assert by_label['Door 1']['cut_width_mm'] == 795
    assert by_label['Door 1']['cut_length_mm'] == 794
    assert all(part['room_id'] == 7 for part in result['sheet_parts'])
    assert not any(part.get('stock_sheet') for part in result['sheet_parts'])
    room = dict(id=7, name='Living Room', items=[dict(id='cab-1', name='Left alcove', result=result)])
    aggregate_result = aggregate([result], catalogue, seed_data['pricing'], rooms=[room])
    sheets = [s for s in aggregate_result['room_stocks'] if s.get('packing_kind') == 'sheet']
    assert sheets
    assert aggregate_result['stock_material_cost'] == sum(catalogue[s['material_id']]['price'] for s in sheets)
    assert aggregate_result['labour_cost'] == 4 * 22.5 + 180


def test_cabinet_presets_and_room_boundary(catalogue, seed_data):
    catalogue = _cabinet_catalogue(catalogue)
    inputs = dict(unit_width=500, unit_height=350, unit_depth=250, divider_count=0,
                  shelves_per_bay=0, door_count=0, workshop_hours=0, installation_days=0)
    seat = calculate_cabinet(inputs, dict(cabinet_preset='window_seat', carcass_material_id='mdf-18mm',
                                          full_top=True, hinged_lid=True), catalogue, seed_data['pricing'], 'seat')
    assert any(p['component'] == 'lid' for p in seat['sheet_parts'])
    assert not any(p['component'] == 'face_frame' for p in seat['sheet_parts'])
    custom = calculate_cabinet(inputs, dict(cabinet_preset='custom', carcass_material_id='mdf-18mm'),
                               catalogue, seed_data['pricing'], 'custom')
    assert not any(p['component'] == 'top_rail' for p in custom['sheet_parts'])
    first = dict(id='seat', name='Window seat', result=seat)
    second = dict(id='custom', name='Cupboard', result=custom)
    together = aggregate([seat, custom], catalogue, seed_data['pricing'],
                         rooms=[dict(id=1, name='One', items=[first, second])])
    separate = aggregate([seat, custom], catalogue, seed_data['pricing'],
                         rooms=[dict(id=1, name='One', items=[first]), dict(id=2, name='Two', items=[second])])
    one = [s for s in together['room_stocks'] if s.get('packing_kind') == 'sheet']
    two = [s for s in separate['room_stocks'] if s.get('packing_kind') == 'sheet']
    assert len(one) < len(two)
    assert {p['wall_name'] for sheet in one for p in sheet['cuts']} == {'Window seat', 'Cupboard'}


def test_custom_cabinet_door_band_and_manual_plinth(catalogue, seed_data):
    catalogue = _cabinet_catalogue(catalogue)
    result = calculate_cabinet(dict(unit_width=504, unit_height=704, unit_depth=400,
        divider_count=0, shelves_per_bay=0, door_count=1,
        plinth_front_back_length=480, plinth_side_length=320,
        plinth_height=100, plinth_front_recess=50, plinth_support_count=2),
        dict(cabinet_preset='custom', carcass_material_id='mdf-18mm',
             sides_enabled=False, bottom_enabled=True, base_type='plinth',
             door_banding='all', sheet_rotation_allowed=False),
        catalogue, seed_data['pricing'], 'custom-1')
    by_label = {part['label']: part for part in result['sheet_parts']}
    assert 'Left side' not in by_label and 'Right side' not in by_label
    assert by_label['Door 1']['finished_width_mm'] == 500
    assert by_label['Door 1']['finished_length_mm'] == 700
    assert by_label['Door 1']['cut_width_mm'] == 498
    assert by_label['Door 1']['cut_length_mm'] == 698
    assert by_label['Plinth front']['cut_length_mm'] == 480
    assert by_label['Plinth left side']['cut_length_mm'] == 320
    assert by_label['Plinth front']['notes'].endswith('50mm from carcass')
    assert 'Plinth support 1' in by_label and 'Plinth support 2' in by_label
    assert not any(part['rotation_allowed'] for part in result['sheet_parts'])


def test_existing_mdf_rips_and_cabinet_rectangles_coexist(catalogue, seed_data):
    panelling = calculate('PANELLING_FULL', 'plain', dict(wall_length=2000, height=800,
        slat_width=100, horizontal_squares=2, vertical_squares=1),
        {'mdf_id':'mdf-9mm'}, catalogue, 3, 'panel')
    cabinet = calculate_cabinet(dict(unit_width=700, unit_height=500, unit_depth=400,
        divider_count=0, shelves_per_bay=0, door_count=0),
        dict(cabinet_preset='custom', carcass_material_id='mdf-9mm'),
        catalogue, seed_data['pricing'], 'cabinet')
    result = aggregate([panelling, cabinet], catalogue, seed_data['pricing'], rooms=[dict(
        id=1, name='Living Room', items=[dict(id='panel', name='Panel wall', result=panelling),
                                         dict(id='cabinet', name='Cabinet', result=cabinet)])])
    mdf = [s for s in result['room_stocks'] if s['material_id'] == 'mdf-9mm']
    assert any(s.get('packing_kind') == 'sheet' for s in mdf)
    assert any(s.get('packing_kind') != 'sheet' for s in mdf)
    assert next(row for row in result['materials'] if row['material_id']=='mdf-9mm')['new_purchase_units'] == len(mdf)


def test_current_quote_cabinet_saves_reopens_and_shows_sheet_plan(app, signed_in):
    client = signed_in
    with app.app_context():
        material = db.session.get(Material, 'mdf-18mm')
        material.label = '18mm MDF sheet'
        material.price = 30
        db.session.commit()
    qid = create_quote(client, app)
    rid = add_room(client, app, qid, 'Living Room')
    assert post_quote(client, app, qid, 'add_item', room_id=rid,
                      name='Left alcove', type='CABINET').status_code == 302
    with app.app_context():
        item_id = db.session.scalar(db.select(WorkItem.id).where(WorkItem.room_id == rid))
    response = post_quote(client, app, qid, 'edit_item', room_id=rid, item_id=item_id,
        name='Left alcove', type='CABINET', subtype='plain', position=0,
        cabinet_preset='alcove', carcass_material_id='mdf-18mm', back_material_id='mdf-9mm',
        door_banding='all', base_type='none', top_rails='on', back_enabled='on',
        face_frame='on', worktop='on', opening_width=1800, unit_width=1600,
        unit_height=800, unit_depth=450, divider_count=1, divider_height=782,
        shelves_per_bay=1, door_count=2, front_overhang=20, workshop_hours=4,
        installation_days=1, plinth_support_count=0)
    assert response.status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        assert quote.result['valid']
        assert quote.rooms[0].items[0].result['sheet_parts']
        assert any(s.get('packing_kind') == 'sheet' for s in quote.result['room_stocks'])
        assert quote.result['stock_material_cost'] == sum(
            quote.snapshot['catalogue'][s['material_id']]['price']
            for s in quote.result['room_stocks'])
    page = client.get(f'/quotes/{qid}')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'Installed Dimensions · Cabinet parts and sheet cut blanks' in html
    assert '<td>797.0 × 796.0</td>' in html
    assert '<td>795.0 × 794.0</td>' in html
    assert 'sheet-diagram' in html
    assert 'Left alcove / Left side' in html
    assert '18mm MDF sheet' in html
    with app.app_context():
        quote = db.session.get(Quote, qid)
        row = next(r for r in material_plan(quote) if r['material_id'] == 'mdf-18mm')
        before_charge = row['chargeable_cost']
        before_need = row['need_to_purchase_quantity']
        assert before_need > 0
    assert post_quote(client, app, qid, 'set_extra_material', room_id=rid,
                      material_id='mdf-18mm', extra_quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        row = next(r for r in material_plan(quote) if r['material_id'] == 'mdf-18mm')
        assert row['extra_quantity'] == 1 and row['room_id'] == rid
        assert row['chargeable_cost'] == before_charge + 30
        need = row['need_to_purchase_quantity']
    assert post_quote(client, app, qid, 'mark_material_purchased', room_id=rid,
                      material_id='mdf-18mm', quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        row = next(r for r in material_plan(quote) if r['material_id'] == 'mdf-18mm')
        assert row['need_to_purchase_quantity'] == need - 1
        assert row['chargeable_cost'] == before_charge + 30
        stock = OwnedStock(material_id='mdf-18mm', stock_type='full', quantity=1)
        db.session.add(stock)
        db.session.commit()
        stock_id = stock.id
    assert post_quote(client, app, qid, 'allocate_owned_stock', room_id=rid,
                      material_id='mdf-18mm', owned_stock_id=stock_id,
                      quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        row = next(r for r in material_plan(quote) if r['material_id'] == 'mdf-18mm')
        assert row['allocated_owned_quantity'] == 1
        assert row['chargeable_cost'] == before_charge + 30
        quote.status = 'Accepted'
        db.session.commit()
    assert '18mm MDF sheet' in client.get('/').get_data(as_text=True)
    with app.app_context():
        quote = db.session.get(Quote, qid)
        quote.rooms[0].items[0].name = '<script>alert(1)</script>'
        reaggregate(quote)
        db.session.commit()
    html = client.get(f'/quotes/{qid}').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html


@pytest.mark.parametrize(('stock_type','length','width'),
                         [('offcut',2000,1000),('full',None,None)])
def test_owned_sheet_reduces_procurement_not_customer_charge(app, stock_type, length, width):
    with app.app_context():
        customer = Customer(name='Cabinet stock customer')
        quote = Quote(customer=customer, title='Two sheet parts', snapshot=current_snapshot())
        room = Room(name='Living Room')
        item = WorkItem(name='Cabinet', type='CABINET', subtype='plain', inputs={}, options={})
        room.items.append(item)
        quote.rooms.append(room)
        db.session.add(quote)
        db.session.flush()
        item.result = dict(valid=True, groups={}, geometry={'workshop_hours':0,'installation_days':0},
            sheet_parts=[dict(id=f'{item.id}:{index}', label=f'Panel {index}',
                material_id='mdf-12mm', cut_length_mm=2000, cut_width_mm=1000,
                rotation_allowed=True, quantity=1) for index in (1, 2)])
        reaggregate(quote)
        row = next(r for r in material_plan(quote) if r['material_id'] == 'mdf-12mm')
        assert row['calculated_quantity'] == 2
        assert row['need_to_purchase_quantity'] == 2
        assert row['chargeable_cost'] == 44
        stock = OwnedStock(material_id='mdf-12mm', stock_type=stock_type,
            usable_length_mm=length, usable_width_mm=width, quantity=1)
        db.session.add(stock)
        db.session.flush()
        db.session.add(OwnedStockAllocation(owned_stock=stock, quote_id=quote.id,
            material_id='mdf-12mm', room_id=room.id, quantity=1,
            stock_length_mm=length or 2440, stock_width_mm=width or 1220))
        db.session.flush()
        row = next(r for r in material_plan(quote) if r['material_id'] == 'mdf-12mm')
        assert row['need_to_purchase_quantity'] == 1
        assert row['chargeable_cost'] == 44
