"""Existing physical pieces reconcile with room cuts without changing customer charges."""
from datetime import date
from copy import deepcopy

from app.models import (db, Customer, Quote, Room, WorkItem, JobPurchase,
                        OwnedStock, OwnedStockAllocation)
from app.services.quotes import current_snapshot, recalculate_item, reaggregate, material_plan
from test_application import post_quote


def quote_with_dado(app, room_lengths):
    customer = Customer(name='Physical stock customer')
    quote = Quote(customer=customer, title='Room physical stock',
                  snapshot=current_snapshot(), full_days=0, extra_hours=0)
    for room_index, lengths in enumerate(room_lengths, 1):
        room = Room(name=f'Room {room_index}', position=room_index)
        for wall_index, length in enumerate(lengths, 1):
            room.items.append(WorkItem(name=f'Wall {wall_index}', type='DADO_STRAIGHT',
                subtype='Dado', inputs={'wall_length': length},
                options={'dado_rail_id': 'dado-45mm-3m'}, position=wall_index))
        quote.rooms.append(room)
    db.session.add(quote)
    db.session.flush()
    for room in quote.rooms:
        for item in room.items:
            recalculate_item(item, quote.snapshot)
    reaggregate(quote)
    db.session.commit()
    return quote


def old_purchase(quote, quantity):
    purchase = JobPurchase(quote=quote, material_id='dado-45mm-1.5m',
                           quantity=quantity, unit_price=3.40, purchased_at=date.today())
    db.session.add(purchase)
    db.session.commit()
    return purchase


def old_reservation(quote, quantity):
    stock = OwnedStock(material_id='dado-45mm-1.5m', stock_type='full',
                       quantity=quantity, reserved_quantity=quantity)
    allocation = OwnedStockAllocation(quote=quote, owned_stock=stock,
                                     material_id=stock.material_id, quantity=quantity)
    db.session.add_all([stock, allocation])
    db.session.commit()
    return allocation


def outstanding(quote):
    return sum(row['need_to_purchase_quantity'] for row in material_plan(quote)
               if row['category'] == 'dado')


def test_single_room_legacy_purchases_and_reservations_reconcile_physical_pieces(app):
    with app.app_context():
        quote = quote_with_dado(app, [[1200, 900]])
        charge = quote.result['chargeable_material_cost']
        assert quote.result['stock_material_cost'] == 5.60  # normal 1 × 2400 mm
        purchase = old_purchase(quote, 2)
        assert purchase.room_id is None and outstanding(quote) == 0
        assert quote.result['chargeable_material_cost'] == charge

        reserved = quote_with_dado(app, [[1200, 900]])
        allocation = old_reservation(reserved, 2)
        assert allocation.room_id is None and outstanding(reserved) == 0


def test_multi_room_legacy_stock_stays_unassigned_until_user_assigns_it(app, signed_in):
    with app.app_context():
        quote = quote_with_dado(app, [[1200], [900]])
        previous_result = deepcopy(quote.result)
        previous_result.pop('room_stocks')
        for row in previous_result['materials']:
            row.pop('room_demands', None)
        quote.result = previous_result
        db.session.commit()
        purchase = old_purchase(quote, 1)
        allocation = old_reservation(quote, 1)
        quote_id, purchase_id, allocation_id = quote.id, purchase.id, allocation.id
        room1, room2 = (room.id for room in quote.rooms)
        assert outstanding(quote) == 2
    page = signed_in.get(f'/quotes/{quote_id}')
    assert page.status_code == 200
    assert page.get_data(as_text=True).count('Unassigned legacy job stock') >= 2
    assert post_quote(signed_in, app, quote_id, 'assign_physical_stock',
                      record_type='purchase', record_id=purchase_id,
                      room_id=room1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        assert outstanding(quote) == 1
        assert db.session.get(OwnedStockAllocation, allocation_id).room_id is None
    assert post_quote(signed_in, app, quote_id, 'assign_physical_stock',
                      record_type='reservation', record_id=allocation_id,
                      room_id=room2).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        assert outstanding(quote) == 0
        assert quote.snapshot['catalogue']['dado-45mm-1.5m']['price'] == 3.40


def test_two_short_pieces_do_not_fake_one_continuous_long_cut(app):
    with app.app_context():
        quote = quote_with_dado(app, [[2900]])
        old_purchase(quote, 2)
        plan = material_plan(quote)
        assert outstanding(quote) == 1
        assert next(row for row in plan if row['need_to_purchase_quantity'])['material_id'] == 'dado-45mm-3m'


def test_assigned_stock_is_room_isolated_and_new_records_capture_room(app, signed_in):
    with app.app_context():
        quote = quote_with_dado(app, [[1200], [900]])
        quote_id = quote.id
        room1, room2 = (room.id for room in quote.rooms)
        purchase = old_purchase(quote, 1)
        purchase.room_id = room1
        stock = OwnedStock(material_id='dado-45mm-1.5m', stock_type='full', quantity=1)
        db.session.add(stock)
        db.session.commit()
        stock_id = stock.id
        assert outstanding(quote) == 1
    assert post_quote(signed_in, app, quote_id, 'allocate_owned_stock',
                      material_id='dado-45mm-1.5m', owned_stock_id=stock_id,
                      room_id=room2, quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        allocation = db.session.scalar(db.select(OwnedStockAllocation).where(
            OwnedStockAllocation.quote_id == quote_id))
        assert allocation.room_id == room2
        assert allocation.stock_length_mm == 1500
        assert outstanding(quote) == 0

        another = quote_with_dado(app, [[1200]])
        another_id, another_room = another.id, another.rooms[0].id
    assert post_quote(signed_in, app, another_id, 'mark_material_purchased',
                      material_id='dado-45mm-1.5m', room_id=another_room,
                      quantity=1).status_code == 302
    with app.app_context():
        another = db.session.get(Quote, another_id)
        recorded = another.purchases[0]
        assert (recorded.room_id, recorded.stock_length_mm, recorded.quantity) == (
            another_room, 1500, 1)
