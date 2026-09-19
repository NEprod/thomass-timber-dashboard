from datetime import date

from app.models import (db, Customer, Quote, Room, WorkItem, Material,
                        OwnedStock, OwnedStockAllocation)
from app.services.inventory import stock_can_satisfy, stock_recommendations
from app.services.quotes import current_snapshot, material_plan, reaggregate
from app.calculations.packing import pack
from test_application import create_quote, add_room, add_item, post_quote
from test_calculations import FULL


def add_stock(client, material_id, stock_type, quantity=1, length='', width='', note=''):
    response = client.post('/materials', data={
        'action': 'add_owned_stock', 'material_id': material_id,
        'stock_type': stock_type, 'usable_length_mm': length,
        'usable_width_mm': width, 'quantity': quantity, 'note': note,
    })
    assert response.status_code == 302


def test_physical_stock_records_reuse_catalogue_products(app, signed_in):
    add_stock(signed_in, 'bead-glass_bead-9x9', 'full', quantity=3, note='Full bead')
    add_stock(signed_in, 'bead-glass_bead-9x9', 'offcut', length=900, quantity=2, note='Bead offcuts')
    add_stock(signed_in, 'mdf-9mm', 'full', quantity=2, note='Full sheets')
    add_stock(signed_in, 'mdf-9mm', 'offcut', length=1200, width=600, note='Sheet offcut')
    with app.app_context():
        rows = db.session.scalars(db.select(OwnedStock).order_by(OwnedStock.id)).all()
        assert [(r.material_id, r.stock_type, r.quantity) for r in rows] == [
            ('bead-glass_bead-9x9', 'full', 3),
            ('bead-glass_bead-9x9', 'offcut', 2),
            ('mdf-9mm', 'full', 2),
            ('mdf-9mm', 'offcut', 1),
        ]
        assert rows[0].usable_length_mm is None
        assert (rows[1].usable_length_mm, rows[1].usable_width_mm) == (900, None)
        assert rows[2].usable_length_mm is None and rows[2].usable_width_mm is None
        assert (rows[3].usable_length_mm, rows[3].usable_width_mm) == (1200, 600)
        assert all(db.session.get(Material, r.material_id) is not None for r in rows)
        sheet_offcut_id = rows[3].id
    response = signed_in.post('/materials', data={
        'action': 'add_owned_stock', 'material_id': 'mdf-9mm', 'stock_type': 'offcut',
        'usable_length_mm': 700, 'usable_width_mm': '', 'quantity': 1,
    })
    assert response.status_code == 200
    assert signed_in.post('/materials', data={
        'action': 'edit_owned_stock', 'stock_id': sheet_offcut_id, 'stock_type': 'offcut',
        'usable_length_mm': 1100, 'usable_width_mm': 550, 'quantity': 1,
        'note': 'Measured again',
    }).status_code == 302
    with app.app_context():
        corrected = db.session.get(OwnedStock, sheet_offcut_id)
        assert (corrected.usable_length_mm, corrected.usable_width_mm, corrected.note) == (1100, 550, 'Measured again')
        assert db.session.scalar(db.select(db.func.count(OwnedStock.id))) == 4


def test_reserve_release_and_double_reservation_preserve_customer_charge(app, signed_in):
    q1 = create_quote(signed_in, app); room1 = add_room(signed_in, app, q1, 'First room')
    add_item(signed_in, app, q1, room1, 'First wall', 'PANELLING_FULL', FULL)
    q2 = create_quote(signed_in, app); room2 = add_room(signed_in, app, q2, 'Second room')
    add_item(signed_in, app, q2, room2, 'Second wall', 'PANELLING_FULL', FULL)
    with app.app_context():
        first = db.session.get(Quote, q1)
        material_id = first.result['materials'][0]['material_id']
        charge = first.result['chargeable_material_cost']
        initial_need = first.result['materials'][0]['need_to_purchase_quantity']
        stock = OwnedStock(material_id=material_id, stock_type='full', quantity=1, note='One full sheet')
        db.session.add(stock); db.session.commit(); stock_id = stock.id
    assert post_quote(signed_in, app, q1, 'allocate_owned_stock', material_id=material_id,
                      owned_stock_id=stock_id, quantity=1).status_code == 302
    with app.app_context():
        first = db.session.get(Quote, q1)
        row = first.result['materials'][0]
        allocation = db.session.scalar(db.select(OwnedStockAllocation).where(OwnedStockAllocation.quote_id == q1))
        assert row['need_to_purchase_quantity'] == initial_need - 1
        assert first.result['chargeable_material_cost'] == charge
        assert db.session.get(OwnedStock, stock_id).reserved_quantity == 1
        allocation_id = allocation.id
    response = post_quote(signed_in, app, q2, 'allocate_owned_stock', material_id=material_id,
                          owned_stock_id=stock_id, quantity=1)
    assert response.status_code == 200
    page = signed_in.get(f'/quotes/{q2}').get_data(as_text=True)
    assert 'One full sheet' in page and 'Reserved — TT-' in page
    assert post_quote(signed_in, app, q1, 'remove_owned_allocation', allocation_id=allocation_id).status_code == 302
    with app.app_context():
        first = db.session.get(Quote, q1)
        assert first.result['materials'][0]['need_to_purchase_quantity'] == initial_need
        assert first.result['chargeable_material_cost'] == charge
        assert db.session.get(OwnedStock, stock_id).reserved_quantity == 0


def test_extra_material_charge_and_completion_consumption_stay_explicit(app, signed_in):
    qid = create_quote(signed_in, app); room = add_room(signed_in, app, qid, 'Job')
    add_item(signed_in, app, qid, room, 'Wall', 'PANELLING_FULL', FULL)
    with app.app_context():
        quote = db.session.get(Quote, qid); material_id = quote.result['materials'][0]['material_id']
        stock = OwnedStock(material_id=material_id, stock_type='full', quantity=1)
        db.session.add(stock); db.session.commit(); stock_id = stock.id
    assert post_quote(signed_in, app, qid, 'set_extra_material', material_id=material_id, extra_quantity=2).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid); charge = quote.result['chargeable_material_cost']
        normal = quote.result['materials'][0]['need_to_purchase_quantity']
    assert post_quote(signed_in, app, qid, 'allocate_owned_stock', material_id=material_id,
                      owned_stock_id=stock_id, quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, qid)
        assert quote.result['materials'][0]['need_to_purchase_quantity'] == normal - 1
        assert quote.result['chargeable_material_cost'] == charge
        customer_id = quote.customer_id
    assert post_quote(signed_in, app, qid, 'details', customer_id=customer_id, title='Complete job',
                      status='Complete', full_days=0, extra_hours=0, measure_at='', quote_date=date.today(),
                      accepted_date='', planned_job_date='', notes='').status_code == 302
    with app.app_context():
        stock = db.session.get(OwnedStock, stock_id)
        allocation = db.session.scalar(db.select(OwnedStockAllocation).where(OwnedStockAllocation.quote_id == qid))
        assert (stock.reserved_quantity, stock.consumed_quantity) == (0, 1)
        assert allocation.consumed


def synthetic_quote(app, material_id, groups):
    customer = Customer(name='Recommendation test')
    quote = Quote(customer=customer, title='Stock recommendation', snapshot=current_snapshot(),
                  full_days=0, extra_hours=0)
    room = Room(name='Room', position=0)
    item = WorkItem(name='Demand', type='PANELLING_FULL', subtype='plain', position=0,
                    inputs={}, options={}, result={'valid': True, 'groups': groups, 'warnings': [],
                    'geometry': {'square_width': 1, 'square_height': 1},
                    'horizontal_strips': 0, 'vertical_strips': 0},
                    pricing_result={'required_panelling_m': 0, 'required_finish_m': 0,
                                    'labour_cost': 0})
    room.items.append(item); quote.rooms.append(room); db.session.add(quote)
    reaggregate(quote); db.session.commit()
    return quote


def linear_group(material_id, lengths, stock_length=2400, kerf=3):
    cuts = [{'id': f'c{i}', 'work_item_id': 'test', 'material_id': material_id,
             'role': 'Test', 'length_mm': length, 'width_mm': 9,
             'label': f'Cut {i}'} for i, length in enumerate(lengths)]
    return {'linear': {'material_id': material_id, 'width_mm': 9,
                       'cuts': cuts, 'strips': pack(cuts, stock_length, kerf)}}


def test_whole_demand_recommendations_only_use_stock_that_reduces_purchase(app, signed_in):
    with app.app_context():
        material_id = 'bead-glass_bead-9x9'
        no_help = synthetic_quote(app, material_id, linear_group(material_id, [1700, 600]))
        short = OwnedStock(material_id=material_id, stock_type='offcut', usable_length_mm=600, quantity=1)
        db.session.add(short); db.session.commit()
        plan = material_plan(no_help)
        recommendation = stock_recommendations(no_help, plan, [short], [])
        assert recommendation[material_id]['stock'] == {}
        assert 'does not reduce' in recommendation[material_id]['text']

        helps = synthetic_quote(app, material_id, linear_group(material_id, [1200, 1200, 1200]))
        useful = OwnedStock(material_id=material_id, stock_type='offcut', usable_length_mm=1200, quantity=1)
        db.session.add(useful); db.session.commit()
        plan = material_plan(helps)
        recommendation = stock_recommendations(helps, plan, [useful], [])
        assert recommendation[material_id]['stock'] == {useful.id: 1}
        assert 'reduces purchase requirement' in recommendation[material_id]['text']


def test_sheet_offcut_dimensions_are_respected_without_new_nesting(app, signed_in):
    with app.app_context():
        material_id = 'mdf-9mm'
        cuts = []
        groups = {}
        for index in range(2):
            cut = {'id': f's{index}', 'work_item_id': 'test', 'material_id': material_id,
                   'role': 'Slat', 'length_mm': 1400, 'width_mm': 600, 'label': 'Slat'}
            cuts.append(cut)
            groups[f'rip{index}'] = {'material_id': material_id, 'width_mm': 600,
                                    'cuts': [cut], 'strips': [dict(cuts=[cut], used_mm=1400,
                                    remainder_mm=1040, kerf_loss_mm=0, index=1)]}
        quote = synthetic_quote(app, material_id, groups)
        half = OwnedStock(material_id=material_id, stock_type='offcut',
                          usable_length_mm=1400, usable_width_mm=600, quantity=1)
        too_short = OwnedStock(material_id=material_id, stock_type='offcut',
                               usable_length_mm=1000, usable_width_mm=1220, quantity=1)
        db.session.add_all([half, too_short]); db.session.commit()
        plan = material_plan(quote)
        assert not stock_can_satisfy(quote, too_short)
        recommendation = stock_recommendations(quote, plan, [half], [])
        assert plan[0]['need_to_purchase_quantity'] == 1
        assert recommendation[material_id]['stock'] == {}
        assert 'does not reduce' in recommendation[material_id]['text']
        quote_id = quote.id
    page = signed_in.get(f'/quotes/{quote_id}').get_data(as_text=True)
    assert '1000 × 1220 mm offcut' in page
    assert 'No current calculated cut fits' in page
