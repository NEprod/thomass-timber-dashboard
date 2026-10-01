from copy import deepcopy

from app.calculations.sections import calculate
from app.calculations.pricing import aggregate
from app.calculations.room_stock import _pack_with_wall_affinity
from app.models import db, Customer, Quote, Room, WorkItem, OwnedStock, JobMaterialState
from app.services.quotes import current_snapshot, recalculate_item, reaggregate, material_plan
from test_application import post_quote


def dado_result(catalogue, work_id, length, *, stair=False):
    kind = 'DADO_STAIR' if stair else 'DADO_STRAIGHT'
    inputs = (dict(wall_length=4000, lower_landing=750, upper_landing=750,
                   slope_length=2900) if stair else dict(wall_length=length))
    return calculate(kind, 'Dado', inputs, {'dado_rail_id': 'dado-45mm-3m'},
                     catalogue, 3, work_id)


def room(room_id, *items):
    return dict(id=room_id, name=f'Room {room_id}',
                items=[dict(id=str(index), name=f'Wall {index}', result=result)
                       for index, result in items])


def plan(catalogue, pricing, rooms):
    return aggregate([item['result'] for room_ in rooms for item in room_['items']],
                     catalogue, pricing, rooms=rooms)


def dado_stocks(result):
    return [stock for stock in result['room_stocks'] if stock['category'] == 'dado']


def test_room_packs_compatible_mdf_from_full_walls_without_losing_cut_origins(catalogue, seed_data):
    inputs=dict(wall_length=2000,height=2000,horizontal_squares=2,
                vertical_squares=1,slat_width=100)
    items=[(index, calculate('PANELLING_FULL','plain',inputs,{'mdf_id':'mdf-9mm'},
                             catalogue,3,str(index))) for index in (1,2)]
    combined=plan(catalogue,seed_data['pricing'],[room(1,*items)])
    separate=plan(catalogue,seed_data['pricing'],[room(1,items[0]),room(2,items[1])])
    sheets=[stock for stock in combined['room_stocks'] if stock['category']=='mdf']
    assert len(sheets)==1
    assert len([stock for stock in separate['room_stocks'] if stock['category']=='mdf'])==2
    finished=[cut for sheet in sheets for rip in sheet['cuts'] for cut in rip['finished_cuts']]
    assert sorted(cut['id'] for cut in finished)==sorted(
        cut['id'] for _,result in items for group in result['groups'].values() for cut in group['cuts'])
    assert {cut['wall_name'] for cut in finished}=={'Wall 1','Wall 2'}
    assert combined['stock_material_cost']==catalogue['mdf-9mm']['price']
    assert all('strips' not in group for _,result in items for group in result['groups'].values())


def test_room_stock_softly_groups_wall_cuts_without_extra_stock():
    cuts=[dict(id=str(index),work_item_id=wall,length_mm=length,label=f'Wall {wall}')
          for index,(wall,length) in enumerate([('A',800),('B',700),('A',600),('B',500)])]
    stocks=_pack_with_wall_affinity(cuts,1500,0)
    assert len(stocks)==2
    assert [{cut['work_item_id'] for cut in stock['cuts']} for stock in stocks]==[{'A'},{'B'}]
    assert sorted(cut['id'] for stock in stocks for cut in stock['cuts'])==sorted(cut['id'] for cut in cuts)


def test_room_keeps_bead_and_ledge_finished_demand_labelled(catalogue, seed_data):
    bead_id=next(key for key,value in catalogue.items()
                 if value['category']=='bead' and value['thickness_mm']==9)
    inputs=dict(wall_length=2000,height=1000,horizontal_squares=2,
                vertical_squares=1,slat_width=100)
    options=dict(mdf_id='mdf-9mm',bead_id=bead_id,ledge_width=18)
    items=[(index,calculate('PANELLING_HALF','ledge_bead',inputs,options,
                            catalogue,3,str(index))) for index in (1,2)]
    result=plan(catalogue,seed_data['pricing'],[room(1,*items)])
    bead_cuts=[cut for stock in result['room_stocks'] if stock['category']=='bead'
               for cut in stock['cuts']]
    ledge_cuts=[cut for stock in result['room_stocks'] if stock['category']=='mdf'
                for rip in stock['cuts'] for cut in rip['finished_cuts'] if cut['role']=='Ledge']
    assert {cut['wall_name'] for cut in bead_cuts}=={'Wall 1','Wall 2'}
    assert {cut['wall_name'] for cut in ledge_cuts}=={'Wall 1','Wall 2'}
    assert len(bead_cuts)==sum(len(group['cuts']) for _,item in items
                               for name,group in item['groups'].items() if 'bead' in name)


def test_six_same_room_dado_walls_share_stock_and_keep_labels(catalogue, seed_data):
    lengths = [900, 600, 450, 350, 300, 200]
    items = [(index, dado_result(catalogue, str(index), length))
             for index, length in enumerate(lengths, 1)]
    result = plan(catalogue, seed_data['pricing'], [room(1, *items)])
    stocks = dado_stocks(result)
    assert len(stocks) == 1 and stocks[0]['stock_length_mm'] == 3000
    assert [cut['length_mm'] for cut in stocks[0]['cuts']] == lengths
    assert {cut['wall_name'] for cut in stocks[0]['cuts']} == {f'Wall {n}' for n in range(1, 7)}
    assert stocks[0]['used_mm'] == sum(lengths) + 3 * (len(lengths) - 1)
    assert stocks[0]['remainder_mm'] == 3000 - stocks[0]['used_mm']
    assert result['stock_material_cost'] == catalogue['dado-45mm-3m']['price']
    assert sum(row['new_purchase_units'] for row in result['materials']) == 1


def test_long_continuous_cut_shares_its_long_stock_remainder(catalogue, seed_data):
    result = plan(catalogue, seed_data['pricing'], [room(1,
        (1, dado_result(catalogue, '1', 4300)),
        (2, dado_result(catalogue, '2', 400)))])
    stocks = dado_stocks(result)
    assert len(stocks) == 1 and stocks[0]['stock_length_mm'] == 4800
    assert [(cut['wall_name'], cut['length_mm']) for cut in stocks[0]['cuts']] == [
        ('Wall 1', 4300), ('Wall 2', 400)]
    assert all(cut['join_id'] is None for cut in stocks[0]['cuts'])
    assert stocks[0]['used_mm'] == 4703 and stocks[0]['remainder_mm'] == 97
    assert result['stock_material_cost'] == catalogue['dado-45mm-4.8m']['price']


def test_rooms_remain_separate_and_stair_members_choose_practical_stock(catalogue, seed_data):
    separate = plan(catalogue, seed_data['pricing'], [
        room(1, (1, dado_result(catalogue, '1', 900))),
        room(2, (2, dado_result(catalogue, '2', 600)))])
    assert len(dado_stocks(separate)) == 2
    assert {stock['room_id'] for stock in dado_stocks(separate)} == {1, 2}

    stair = dado_result(catalogue, 'stair', 0, stair=True)
    result = plan(catalogue, seed_data['pricing'], [room(1, (1, stair))])
    stocks = dado_stocks(result)
    assert [stock['stock_length_mm'] for stock in stocks] == [4500]
    cuts = [cut for stock in stocks for cut in stock['cuts']]
    assert sorted(cut['length_mm'] for cut in cuts) == [750, 750, 2900]
    assert {cut['role'] for cut in cuts} == {'Lower landing dado', 'Slope dado', 'Upper landing dado'}
    assert sum(stock['kerf_loss_mm'] for stock in stocks) == 6
    available = {key: value for key, value in catalogue.items()
                 if value['category'] != 'dado' or value['profile'] != '45mm'
                 or value['length_mm'] in (1800, 3000, 4800)}
    stair_with_available = dado_result(available, 'stair', 0, stair=True)
    practical = plan(available, seed_data['pricing'], [room(1, (1, stair_with_available))])
    assert sorted(stock['stock_length_mm'] for stock in dado_stocks(practical)) == [1800, 3000]
    single = plan(catalogue, seed_data['pricing'], [room(1, (1, dado_result(catalogue, '1', 2900)))])
    assert dado_stocks(single)[0]['stock_length_mm'] == 3000


def test_current_quote_opens_and_recalculation_uses_saved_prices(app, signed_in):
    with app.app_context():
        customer = Customer(name='Room packing customer')
        quote = Quote(customer=customer, title='Existing saved quote', snapshot=current_snapshot(),
                      full_days=0, extra_hours=0)
        living = Room(name='Living room', position=0)
        for index, length in enumerate((900, 600), 1):
            item = WorkItem(name=f'Wall {index}', type='DADO_STRAIGHT', subtype='Dado',
                            inputs={'wall_length': length},
                            options={'dado_rail_id': 'dado-45mm-3m'}, position=index)
            living.items.append(item)
        quote.rooms.append(living)
        db.session.add(quote)
        db.session.flush()
        for item in living.items:
            recalculate_item(item, quote.snapshot)
        quote.material_states.append(JobMaterialState(material_id='dado-45mm-1.5m',
                                                       room_id=living.id, extra_quantity=1))
        reaggregate(quote)
        extra_charge = quote.result['extra_material_cost']
        saved_snapshot = deepcopy(quote.snapshot)
        saved_snapshot['catalogue']['dado-45mm-1.8m']['price'] = 77
        quote.snapshot = saved_snapshot
        db.session.commit()
        quote_id, room_id, item_id = quote.id, living.id, living.items[0].id
        snapshot = deepcopy(quote.snapshot)
    page = signed_in.get(f'/quotes/{quote_id}')
    assert page.status_code == 200 and b'Existing saved quote' in page.data
    response = post_quote(signed_in, app, quote_id, 'edit_item', room_id=room_id,
                          item_id=item_id, name='Wall 1', type='DADO_STRAIGHT',
                          subtype='Dado', wall_length=900, dado_rail_id='dado-45mm-3m',
                          position=1)
    assert response.status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        assert quote.snapshot == snapshot
        assert [item.name for item in quote.rooms[0].items] == ['Wall 1', 'Wall 2']
        assert len(dado_stocks(quote.result)) == 1
        assert quote.result['extra_material_cost'] == extra_charge
        assert any(row['material_id'] == 'dado-45mm-1.5m' and row['extra_quantity'] == 1
                   for row in quote.result['materials'])
        normal_charge = quote.result['chargeable_material_cost']
        material_id = dado_stocks(quote.result)[0]['material_id']
        stock = OwnedStock(material_id=material_id, stock_type='full', quantity=1)
        db.session.add(stock)
        db.session.commit()
        stock_id = stock.id
        assert material_plan(quote)[0]['need_to_purchase_quantity'] == 1
    assert post_quote(signed_in, app, quote_id, 'allocate_owned_stock',
                      material_id=material_id, owned_stock_id=stock_id,
                      quantity=1).status_code == 302
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        assert material_plan(quote)[0]['need_to_purchase_quantity'] == 0
        assert quote.result['chargeable_material_cost'] == normal_charge


def test_straight_square_dimensions_and_dashboard_acceptance(app, signed_in):
    with app.app_context():
        customer = Customer(name='Dado customer')
        quote = Quote(customer=customer, title='Bottom dado squares', snapshot=current_snapshot(),
                      full_days=0, extra_hours=0)
        living = Room(name='Living room', position=0)
        item = WorkItem(name='Bottom wall', type='DADO_STRAIGHT',
                        subtype='Dado Squares Bottom',
                        inputs=dict(wall_length=3000, gap_width=100,
                                    bottom_squares=4, bottom_zone_height=1000),
                        options={'dado_rail_id': 'dado-45mm-3m',
                                 'dado_square_id': 'dado-45mm-3m'}, position=0)
        living.items.append(item)
        quote.rooms.append(living)
        db.session.add(quote)
        db.session.flush()
        recalculate_item(item, quote.snapshot)
        reaggregate(quote)
        db.session.commit()
        quote_id = quote.id
        assert item.result['geometry']['square_width'] == 625
        assert item.result['geometry']['square_height'] == 800
    quote_page = signed_in.get(f'/quotes/{quote_id}').get_data(as_text=True)
    assert 'Square dimensions' in quote_page and '625.0 × 800.0' in quote_page
    assert 'Cut Summary' in quote_page and 'Room cut plan' in quote_page
    assert 'Item stock preview' not in quote_page
    assert quote_page.count('<h4>Living room</h4>') == 1
    assert 'Material to purchase' in quote_page
    assert 'Bottom dado squares' not in signed_in.get('/').get_data(as_text=True).split('Materials to buy')[1]
    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        quote.status = 'Accepted'
        db.session.commit()
    assert 'Bottom dado squares' in signed_in.get('/').get_data(as_text=True).split('Materials to buy')[1]
