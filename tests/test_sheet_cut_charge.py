"""Charge recorded guillotine operations once, independently of build labour."""
from copy import deepcopy

import pytest

from app.calculations.preparation import sheet_cut_operation_count
from app.calculations.pricing import aggregate
from app.calculations.room_stock import pack_rooms
from app.services.quotes import reaggregate
from app.services.stock_plans import prepare_stock_views
from app.models import db, WorkItem
from test_cabinet_refinements import cabinet, room
from test_spare_material import make_quote, extra


def splits(node):
    return 0 if node['kind'] != 'split' else 1 + splits(node['first']) + splits(node['second'])


def test_shared_guillotine_cut_charged_once(catalogue, seed_data):
    # Two full-width parts separated by one shared guillotine operation.
    parts = [dict(id=str(i), material_id='mdf-18mm', label=f'Part {i}',
                  cut_length_mm=2440, cut_width_mm=w, rotation_allowed=False)
             for i, w in enumerate((600, 617), 1)]
    result = dict(valid=True, groups={}, sheet_parts=parts, geometry={})
    config = dict(seed_data['pricing'], sheet_edge_trim=0, sheet_kerf=3, cut_cost_per_strip=3.25)
    rooms = [room(result)]
    before = deepcopy(result)
    materials, stocks = pack_rooms(rooms, catalogue, config['kerf'], sheet_trim=0, sheet_kerf=3)
    priced = aggregate([result], catalogue, config, rooms=rooms)
    assert priced['room_stocks'] == stocks and priced['materials'] == materials
    assert result == before
    assert len(stocks) == 1 and len(stocks[0]['cuts']) == 2
    assert len(stocks[0]['sheet_cut_lines']) == splits(stocks[0]['sheet_tree']) == 1
    assert priced['sheet_cut_operations'] == 1 and priced['total_prepared_strips'] == 0
    assert priced['cut_cost'] == 3.25
    assert priced['labour_cost'] == 0
    assert prepare_stock_views(stocks)[0]['sheet_cut_operations'] == 1


@pytest.mark.parametrize('preset', ['alcove', 'window_seat', 'bench', 'custom'])
def test_all_cabinet_presets_charge_split_tree_keep_plan_and_labour(catalogue, seed_data, preset):
    result = cabinet(catalogue, seed_data['pricing'], inputs={'opening_width': 704},
        options={'cabinet_preset': preset})
    before = deepcopy(result)
    rooms = [room(result)]
    config = seed_data['pricing']
    materials, stocks = pack_rooms(rooms, catalogue, config['kerf'],
        sheet_trim=config['sheet_edge_trim'], sheet_kerf=config['sheet_kerf'])
    priced = aggregate([result], catalogue, config, rooms=rooms)
    count = sum(splits(s['sheet_tree']) for s in stocks if s.get('packing_kind') == 'sheet')
    assert count > 0
    assert priced['sheet_cut_operations'] == sheet_cut_operation_count(stocks) == count
    assert priced['cut_cost'] == count * config['cut_cost_per_strip']
    assert priced['room_stocks'] == stocks and priced['materials'] == materials
    assert result == before
    assert priced['stock_material_cost'] == sum(m['cost'] for m in materials)
    assert priced['labour_cost'] == result['geometry']['workshop_hours'] * config['hourly_rate'] + result['geometry']['installation_days'] * config['day_rate']


def test_linear_pse_cuts_do_not_add_sheet_operations(catalogue, seed_data):
    result = cabinet(catalogue, seed_data['pricing'], inputs={'opening_width': 704},
        options={'worktop_type': 'pse', 'pse_material_id': 'pse-100x25-2.4m'})
    priced = aggregate([result], catalogue, seed_data['pricing'], rooms=[room(result)])
    assert any(s['category'] == 'pse' for s in priced['room_stocks'])
    count = sum(len(s['sheet_cut_lines']) for s in priced['room_stocks'] if s.get('packing_kind') == 'sheet')
    assert priced['cut_cost'] == count * seed_data['pricing']['cut_cost_per_strip']
    assert priced['total_prepared_strips'] == 0


def test_mixed_room_dimensional_repacking_retains_sheet_operations(app):
    with app.app_context():
        q = make_quote()
        unit = WorkItem(name='Cabinet', type='CABINET', subtype='plain', inputs={}, options={})
        q.rooms[0].items.append(unit)
        db.session.flush()
        unit.result = cabinet(q.snapshot['catalogue'], q.snapshot['pricing'], item_id=str(unit.id))
        reaggregate(q)
        before = deepcopy(q.result)
        nested = [deepcopy(s) for s in before['room_stocks'] if s.get('packing_kind') == 'sheet']
        assert before['sheet_cut_operations'] > 0
        extra(q, 2)
        assert q.result['sheet_cut_operations'] == before['sheet_cut_operations']
        assert q.result['total_prepared_strips'] == before['total_prepared_strips'] + 2
        assert q.result['cut_cost'] == before['cut_cost'] + 2 * q.snapshot['pricing']['cut_cost_per_strip']
        assert [s for s in q.result['room_stocks'] if s.get('packing_kind') == 'sheet'] == nested
        assert q.result['labour_cost'] == before['labour_cost']


def test_separate_room_splits_charged_independently(catalogue, seed_data):
    first = cabinet(catalogue, seed_data['pricing'], item_id='one')
    second = cabinet(catalogue, seed_data['pricing'], item_id='two')
    rooms = [room(first, room_id=1), room(second, room_id=2)]
    priced = aggregate([first, second], catalogue, seed_data['pricing'], rooms=rooms)
    count = sum(splits(s['sheet_tree']) for s in priced['room_stocks'])
    assert {s['room_id'] for s in priced['room_stocks']} == {1, 2}
    assert priced['sheet_cut_operations'] == count
    assert priced['cut_cost'] == count * seed_data['pricing']['cut_cost_per_strip']
