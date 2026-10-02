"""Prepared MDF strip charging follows Workshop Preparation, including extras."""
from copy import deepcopy

import pytest

from app.models import db, Quote
from app.calculations.preparation import prepared_strip_count
from app.calculations.pricing import aggregate
from app.services.dimensional_extras import with_dimensional_extras, strip_payload
from app.services.quotes import recalculate_item, reaggregate
from app.services.spare_material import recommendations, exact_plan
from app.services.stock_plans import prepare_stock_views
from test_spare_material import make_quote, extra
from test_application import post_quote


def representative():
    q = make_quote()
    item = q.rooms[0].items[0]
    item.inputs = dict(wall_length=4000, height=1000, horizontal_squares=7,
        vertical_squares=1, slat_width=100, lower_landing=1000,
        upper_landing=1000, slope_length=2800)
    recalculate_item(item, q.snapshot)
    reaggregate(q)
    db.session.commit()
    return q


def assert_preparation_agrees(q, count, charge):
    views = prepare_stock_views(q.result['room_stocks'], q.rooms)
    assert prepared_strip_count(q.result['room_stocks']) == count
    assert sum(v['prepared_strip_count'] for v in views) == count
    assert sum(len(v['strips']) for v in views) == count
    assert q.result['total_prepared_strips'] == count
    assert q.result['strip_cut_rate'] == q.snapshot['pricing']['cut_cost_per_strip']
    assert q.result['cut_cost'] == charge


@pytest.mark.parametrize(('selected', 'count', 'charge'), [(0, 8, 16), (1, 9, 18), (2, 10, 20)])
def test_representative_selection_and_same_sheet_charge(app, signed_in, selected, count, charge):
    with app.app_context():
        q = representative()
        qid, rid = q.id, q.rooms[0].id
        item = q.rooms[0].items[0]
        before, geometry = deepcopy(q.result), deepcopy(item.result)
        assert (item.result['horizontal_strips'], item.result['vertical_strips']) == (5, 4)
        assert_preparation_agrees(q, 8, 16)
        rec = recommendations(q)[0]
        assert rec['quantity'] == 2
        assert all(p['additional_stock'] == 0 and p['incremental_cost'] == 0 for p in rec['previews'])
    if selected:
        assert post_quote(signed_in, app, qid, 'add_recommended_spares', room_id=rid,
            **{'spare_' + rec['id']: selected}).status_code == 302
    with app.app_context():
        q = db.session.get(Quote, qid)
        assert_preparation_agrees(q, count, charge)
        assert len(q.result['room_stocks']) == 1
        assert q.result['stock_material_cost'] == before['stock_material_cost']
        assert q.result['chargeable_material_cost'] == before['chargeable_material_cost'] + 2 * selected
        assert q.rooms[0].items[0].result == geometry
        for key in ('mastic_units', 'mastic_cost', 'labour_cost', 'take_home', 'delivery_cost', 'paid_total'):
            assert q.result[key] == before[key]
        assert sum(p['quantity'] for s in q.material_states for p in s.dimensional_extras or []) == selected


def test_extra_sheet_threshold_and_removal_charge(app, signed_in):
    with app.app_context():
        q = make_quote(('tight',))
        assert_preparation_agrees(q, 11, 22)
        before = deepcopy(q.result)
        state = extra(q, 1)
        qid, sid = q.id, state.id
        assert_preparation_agrees(q, 12, 24)
        price = q.snapshot['catalogue']['mdf-9mm']['price']
        assert len(q.result['room_stocks']) == 2
        assert q.result['stock_material_cost'] == before['stock_material_cost'] + price
        assert q.result['chargeable_material_cost'] == before['chargeable_material_cost'] + price + 2
    assert post_quote(signed_in, app, qid, 'set_dimensional_extra', state_id=sid,
        extra_index=0, quantity=0).status_code == 302
    with app.app_context():
        q = db.session.get(Quote, qid)
        assert_preparation_agrees(q, 11, 22)
        assert len(q.result['room_stocks']) == 1
        assert q.result['chargeable_material_cost'] == before['chargeable_material_cost']


def test_preview_and_acceptance_share_saved_rate_without_mutation(app):
    with app.app_context():
        q = representative()
        snapshot = deepcopy(q.snapshot)
        snapshot['pricing']['cut_cost_per_strip'] = 3.25
        q.snapshot = snapshot
        reaggregate(q)
        before = deepcopy(q.result)
        exact = exact_plan(q)
        payload = strip_payload(q.snapshot['catalogue']['mdf-9mm'], 100, 2440, 2)
        preview = with_dimensional_extras(q, exact, {(q.rooms[0].id, 'mdf-9mm'): [payload]})
        assert preview['total_prepared_strips'] == 10 and preview['cut_cost'] == 32.5
        assert preview['material_cost'] == exact['material_cost'] + 6.5
        assert q.result == before and not q.material_states
        extra(q, 2)
        assert_preparation_agrees(q, 10, 32.5)
        assert q.result['room_stocks'] == preview['room_stocks']
        assert q.result['material_cost'] == preview['material_cost']


def test_no_room_aggregate_also_uses_packed_strips(app):
    with app.app_context():
        q = representative()
        result = aggregate([q.rooms[0].items[0].result], q.snapshot['catalogue'], q.snapshot['pricing'])
        assert result['total_prepared_strips'] == 8 and result['cut_cost'] == 16


def test_nested_cabinet_parts_are_not_prepared_strips(catalogue, seed_data):
    from test_cabinet_refinements import cabinet
    result = cabinet(catalogue, seed_data['pricing'])
    rooms = [dict(id=1, name='Cabinet', items=[dict(id='1', name='Cabinet', result=result)])]
    priced = aggregate([result], catalogue, seed_data['pricing'], rooms=rooms)
    assert priced['room_stocks'] and any(s.get('packing_kind') == 'sheet' for s in priced['room_stocks'])
    assert priced['total_prepared_strips'] == 0
    assert priced['cut_cost'] == priced['sheet_cut_operations'] * seed_data['pricing']['cut_cost_per_strip']
    assert sum(v['prepared_strip_count'] for v in prepare_stock_views(priced['room_stocks'])) == 0
