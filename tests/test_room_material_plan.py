from datetime import date

from app.models import (db, Customer, Quote, Room, WorkItem, JobMaterialState,
                        JobPurchase, OwnedStock, OwnedStockAllocation)
from app.services.quotes import current_snapshot, recalculate_item, reaggregate, material_plan
from test_application import post_quote
from test_calculations import FULL


def _multi_room_quote(app):
    customer = Customer(name='Material plan customer')
    quote = Quote(customer=customer, title='Grouped plan', snapshot=current_snapshot(),
                  full_days=0, extra_hours=0)
    for index, name in enumerate(('Living room', 'Hall & stairs')):
        room = Room(name=name, position=index)
        if index == 0:
            room.items.append(WorkItem(name='Full wall', type='PANELLING_FULL', subtype='plain',
                inputs=dict(FULL), options={'mdf_id': 'mdf-9mm'}, position=0))
        room.items.append(WorkItem(name=f'Dado wall {index}', type='DADO_STRAIGHT',
            subtype='Dado', inputs={'wall_length': 1500 + index * 100, 'gap_width': 100},
            options={'dado_rail_id': 'dado-45mm-3m'}, position=index + 1))
        quote.rooms.append(room)
    db.session.add(quote)
    db.session.flush()
    for room in quote.rooms:
        for item in room.items:
            recalculate_item(item, quote.snapshot)
    reaggregate(quote)
    db.session.commit()
    return quote


def test_room_grouped_extra_and_purchase_actions_use_known_room(app, signed_in):
    with app.app_context():
        quote = _multi_room_quote(app)
        quote_id = quote.id
        living, hall = [room.id for room in quote.rooms]
        material_id = quote.result['materials'][0]['material_id']
        before_material_charge = quote.result['chargeable_material_cost']
        room_materials = material_plan(quote)
        assert any(row['room_id'] == living and row['category'] == 'mdf' for row in room_materials)
        assert any(row['room_id'] == hall and row['category'] == 'dado' for row in room_materials)
    page = signed_in.get(f'/quotes/{quote_id}').get_data(as_text=True)
    assert 'Living room' in page and 'Hall &amp; stairs' in page
    assert 'material-plan-row' in page and 'Reserved pieces</th>' not in page
    assert 'class="material-table"' in page
    for heading in ('Calculated', 'Extra', 'Total', 'Reserved', 'Material to purchase', 'Charge', 'Actions'):
        assert f'<th scope="col">{heading}</th>' in page
    assert 'Save Extra' not in page and 'Mark purchased' in page
    assert 'Owned stock & reservations' in page
    assert 'Quote-level material' in page
    assert 'Quote consumables' in page and 'Additional charges' in page and 'Customer payments' in page
    assert 'quote-total-panel' in page
    assert 'Mastic ·' in page and 'Cut charge' in page and 'Delivery' in page
    assert 'Saved price snapshot' in page and 'Edit saved charge or payment' in page
    assert '<select name="room_id"' not in page

    assert post_quote(signed_in, app, quote_id, 'set_extra_material',
                      material_id=material_id, room_id=living, extra_quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        extra = db.session.scalar(db.select(JobMaterialState).where(
            JobMaterialState.quote_id == quote_id, JobMaterialState.room_id == living))
        assert extra.material_id == material_id and extra.extra_quantity == 1
        assert quote.result['chargeable_material_cost'] > before_material_charge
        plan = [row for row in material_plan(quote) if row['material_id'] == material_id]
        assert next(row for row in plan if row['room_id'] == living)['extra_quantity'] == 1
        hall_row = next(row for row in material_plan(quote) if row['room_id'] == hall)
        assert hall_row['extra_quantity'] == 0
        hall_material_id = hall_row['material_id']
        purchase_qty = hall_row['need_to_purchase_quantity']
        assert purchase_qty > 0
        totals_after_extra = (quote.result['chargeable_material_cost'], quote.result['final_price'],
                              quote.result['deposit_required'])
    assert post_quote(signed_in, app, quote_id, 'mark_material_purchased',
                      material_id=hall_material_id, room_id=hall, quantity=1,
                      purchased_at=date.today().isoformat()).status_code == 302
    with app.app_context():
        purchase = db.session.scalar(db.select(JobPurchase).where(JobPurchase.quote_id == quote_id))
        assert purchase.room_id == hall
        stock = OwnedStock(material_id=hall_material_id, stock_type='full', quantity=1)
        db.session.add(stock)
        db.session.commit()
        stock_id = stock.id
    assert post_quote(signed_in, app, quote_id, 'allocate_owned_stock',
                      material_id=hall_material_id, room_id=hall, owned_stock_id=stock_id,
                      quantity=1).status_code == 302
    with app.app_context():
        allocation = db.session.scalar(db.select(OwnedStockAllocation).where(
            OwnedStockAllocation.quote_id == quote_id))
        assert allocation.room_id == hall
        quote = db.session.get(Quote, quote_id)
        assert (quote.result['chargeable_material_cost'], quote.result['final_price'],
                quote.result['deposit_required']) == totals_after_extra


def test_legacy_extra_room_resolution_and_assignment_preserve_totals(app, signed_in):
    with app.app_context():
        quote = _multi_room_quote(app)
        quote_id = quote.id
        _, room_b = [room.id for room in quote.rooms]
        extra = JobMaterialState(material_id='dado-45mm-3m', extra_quantity=2)
        quote.material_states.append(extra)
        reaggregate(quote)
        db.session.commit()
        extra_id = extra.id
        before = (quote.result['extra_material_cost'], quote.result['chargeable_material_cost'],
                  quote.result['final_price'], quote.result['deposit_required'])
        assert len([row for row in quote.material_states if row.material_id == extra.material_id]) == 1
        assert any(row.get('is_legacy_extra') and row['extra_quantity'] == 2
                   for row in material_plan(quote))
    page = signed_in.get(f'/quotes/{quote_id}').get_data(as_text=True)
    assert 'Unassigned legacy Extra Material' in page
    assert 'Assign Extra Material' in page
    assert post_quote(signed_in, app, quote_id, 'assign_extra_material',
                      state_id=extra_id, room_id=room_b).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        state = db.session.get(JobMaterialState, extra_id)
        assert state.room_id == room_b and state.extra_quantity == 2
        assert len([row for row in quote.material_states if row.material_id == state.material_id]) == 1
        assert (quote.result['extra_material_cost'], quote.result['chargeable_material_cost'],
                quote.result['final_price'], quote.result['deposit_required']) == before
        row = next(row for row in material_plan(quote)
                   if row['material_id'] == state.material_id and row['room_id'] == room_b)
        assert row['extra_quantity'] == 2


def test_single_room_legacy_extra_resolves_without_duplication(app):
    with app.app_context():
        quote = _multi_room_quote(app)
        room = quote.rooms[0]
        quote.rooms.remove(quote.rooms[1])
        state = JobMaterialState(material_id='dado-45mm-3m', extra_quantity=1)
        quote.material_states.append(state)
        db.session.flush()
        rows = [row for row in material_plan(quote)
                if row['material_id'] == state.material_id and row['extra_quantity']]
        assert len(rows) == 1 and rows[0]['room_id'] == room.id
        assert state.room_id is None  # runtime compatibility does not rewrite records
