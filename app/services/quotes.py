from copy import deepcopy
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_CEILING
from ..models import (db, Material, PricingConfig, Quote, JobMaterialState,
                      JobPurchase, OwnedStockAllocation, now)
from ..calculations.sections import calculate
from ..calculations.packing import CalculationError
from ..calculations.pricing import aggregate, money
from .room_procurement import procurement_plan, assigned_room

def current_snapshot():
    config=db.session.get(PricingConfig,1)
    if config is None: raise CalculationError('Run flask init-db to seed the catalogue.')
    return {'captured_at':now().isoformat(),'catalogue':{m.id:m.as_dict() for m in db.session.scalars(db.select(Material))},'pricing':deepcopy(config.values)}

def recalculate_item(item, snapshot):
    try:
        item.result=calculate(item.type,item.subtype,item.inputs,item.options,snapshot['catalogue'],snapshot['pricing']['kerf'],item.id,snapshot['pricing'].get('coving_kerf',10))
        groups=item.result['groups']
        slat=sum(sum(c['length_mm'] for c in g['cuts']) for k,g in groups.items() if snapshot['catalogue'][g['material_id']]['category']=='mdf' and k!='ledge')/1000
        finish=sum(sum(c['length_mm'] for c in g['cuts']) for k,g in groups.items() if snapshot['catalogue'][g['material_id']]['category']=='bead' or k=='ledge')/1000
        dado=sum(sum(c['length_mm'] for c in g['cuts']) for g in groups.values() if snapshot['catalogue'][g['material_id']]['category']=='dado')/1000
        coving=sum(sum(c['length_mm'] for c in g['cuts']) for g in groups.values() if snapshot['catalogue'][g['material_id']]['category']=='coving')/1000
        item.pricing_result={'required_panelling_m':slat,'required_finish_m':finish+dado,'required_dado_m':dado,'required_coving_m':coving,'labour_cost':money(slat*snapshot['pricing']['mdf_slat_per_m_gbp']+finish*snapshot['pricing']['bead_per_m_gbp']+dado*snapshot['pricing']['dado_per_m_gbp']+coving*snapshot['pricing'].get('coving_per_m_gbp',6.5))}
    except CalculationError as exc:
        item.result={'valid':False,'errors':[str(exc)],'groups':{},'warnings':[]}
        item.pricing_result={}

def _up_to_ten(value):
    return float((Decimal(str(value)) / Decimal('10')).to_integral_value(rounding=ROUND_CEILING) * Decimal('10'))


def material_plan(quote, result=None):
    """Join pure calculator demand to explicit quote procurement state.

    Calculator demand remains the customer charge baseline. Owned stock only
    changes what the workshop still needs to buy, never the customer price.
    """
    result = result or quote.result or {}
    states = defaultdict(list)
    for state in quote.material_states:
        states[state.material_id].append(state)
    rows = db.session.scalars(db.select(OwnedStockAllocation).where(OwnedStockAllocation.quote_id == quote.id)).all()
    room_needs, unused_full = procurement_plan(quote, result)
    persisted_material_rows = [row for row in result.get('materials', [])
                               if not row.get('is_calculated_consumable')]
    normal = {}
    for row in persisted_material_rows:
        material_id = row['material_id']
        if material_id not in normal:
            normal[material_id] = dict(row)
        elif row.get('room_id') is not None:
            normal[material_id]['calculated_quantity'] = (
                normal[material_id].get('calculated_quantity', 0) + row.get('calculated_quantity', 0))
    for material_id, row in normal.items():
        if row.get('room_id') is not None:
            row['new_purchase_units'] = row.get('calculated_quantity', row.get('new_purchase_units', 0))
    needed_ids = {material_id for _, material_id in room_needs}
    material_ids = list(normal) + sorted((needed_ids | set(states)) - set(normal))
    plan = []
    for material_id in material_ids:
        calculated = normal.get(material_id)
        product = quote.snapshot['catalogue'].get(material_id, {})
        extra_by_room = defaultdict(int)
        unassigned_states = []
        for state in states[material_id]:
            room_id = assigned_room(quote, state)
            if room_id is None:
                unassigned_states.append(state)
            else:
                extra_by_room[room_id] += state.extra_quantity
        stock_units = Counter()
        for stock in result.get('room_stocks', []):
            if stock['material_id'] == material_id:
                stock_units[stock['room_id']] += 1
        room_ids = [room.id for room in quote.rooms
                    if stock_units[room.id] or extra_by_room[room.id] or
                    room_needs[(room.id, material_id)]]
        unused = unused_full[material_id]
        for room_id in room_ids:
            room = next(entry for entry in quote.rooms if entry.id == room_id)
            extra = extra_by_room[room_id]
            calculated_units = stock_units[room_id]
            units_needed = room_needs[(room_id, material_id)]
            extra_offset = min(extra, unused)
            unused -= extra_offset
            extra_need = max(0, extra - extra_offset)
            allocated = sum(a.quantity for a in rows if a.material_id == material_id and
                            assigned_room(quote, a) == room_id)
            purchased = sum(p.quantity for p in quote.purchases if p.material_id == material_id and
                            assigned_room(quote, p) == room_id)
            row = dict(calculated) if calculated else dict(
                material_id=material_id, label=product.get('label', material_id),
                category=product.get('category', 'other'), new_purchase_units=0,
                cost=0, room_demands=[])
            row.update(room_id=room_id, room_name=room.name if room else None,
                       calculated_quantity=calculated_units, extra_quantity=extra,
                       total_quantity=calculated_units + extra,
                       allocated_owned_quantity=allocated, purchased_quantity=purchased,
                       need_to_purchase_quantity=units_needed + extra_need,
                       room_purchase_units=[], extra_need_units=extra_need,
                       unit_price=product.get('price', 0),
                       chargeable_cost=money(calculated_units * product.get('price', 0) +
                                             extra * product.get('price', 0)))
            plan.append(row)
        for legacy_state in unassigned_states:
            # One legacy row stays one row, remains in the quote total, and is
            # never copied into every room's demand.
            plan.append(dict(material_id=material_id, label=product.get('label', material_id),
                category=product.get('category', 'other'), room_id=None,
                room_name='Unassigned legacy Extra Material', legacy_unassigned=True,
                calculated_quantity=0, extra_quantity=legacy_state.extra_quantity,
                total_quantity=legacy_state.extra_quantity, allocated_owned_quantity=0,
                purchased_quantity=0, need_to_purchase_quantity=0, unit_price=product.get('price', 0),
                chargeable_cost=money(legacy_state.extra_quantity * product.get('price', 0)),
                is_legacy_extra=True, legacy_state_id=legacy_state.id))
    mastic_units = int(result.get('mastic_units', 0) or 0)
    if mastic_units:
        mastic_cost = money(result.get('mastic_cost', 0))
        config = db.session.get(PricingConfig, 1)
        on_hand = int(config.values.get('mastic_on_hand', 0)) if config else 0
        purchased = sum(p.quantity for p in quote.purchases if p.material_id == 'calculated-mastic')
        plan.append(dict(material_id='calculated-mastic', label='Mastic',
                         category='consumable', is_calculated_consumable=True,
                         calculated_quantity=mastic_units, extra_quantity=0,
                         total_quantity=mastic_units, allocated_owned_quantity=on_hand,
                         purchased_quantity=purchased,
                         need_to_purchase_quantity=max(0, mastic_units - on_hand - purchased),
                         unit_price=money(mastic_cost / mastic_units),
                         chargeable_cost=mastic_cost, room_id=None, room_name=None,
                         is_quote_level=True))
    return plan


def reaggregate(quote):
    # Room IDs are part of the persisted stock plan, including newly added rooms.
    db.session.flush()
    rooms=[dict(id=room.id, name=room.name,
                items=[dict(id=item.id, name=item.name, result=item.result) for item in room.items])
           for room in quote.rooms]
    result=aggregate([item['result'] for room in rooms for item in room['items']],
                     quote.snapshot['catalogue'],quote.snapshot['pricing'],
                     quote.full_days,quote.extra_hours,rooms=rooms)
    plan = material_plan(quote, result)
    extra_material_cost = money(sum(row['extra_quantity'] * row['unit_price'] for row in plan))
    chargeable_material_cost = money(result['material_cost'] + extra_material_cost)
    consumable_cost = money(sum(row.quantity * row.unit_price for row in quote.consumables))
    additional_cost = money(sum(row.amount for row in quote.additional_charges))
    paid = money(sum(row.amount for row in quote.payments))
    deposit_base = money(chargeable_material_cost + consumable_cost + additional_cost)
    final = _up_to_ten(money(deposit_base + result['take_home'])) if result['valid'] else None
    result.update(materials=plan, extra_material_cost=extra_material_cost,
                  chargeable_material_cost=chargeable_material_cost,
                  consumable_cost=consumable_cost, additional_charge_cost=additional_cost,
                  deposit_required=_up_to_ten(deposit_base) if result['valid'] else None,
                  paid_total=paid, balance=money(max(0, (final or 0) - paid)),
                  payment_status='Paid in full' if final and paid >= final else ('Part paid' if paid else 'Unpaid'),
                  final_price=final)
    quote.result=result
    quote.updated_at=now()


def refresh_prices(quote):
    quote.snapshot=current_snapshot()
    for room in quote.rooms:
        for item in room.items: recalculate_item(item,quote.snapshot)
    reaggregate(quote)
