from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
from ..models import (db, Material, PricingConfig, Quote, JobMaterialState,
                      JobPurchase, OwnedStockAllocation, now)
from ..calculations.sections import calculate
from ..calculations.packing import CalculationError
from ..calculations.pricing import aggregate, money
from .inventory import procurement_units
from .room_procurement import procurement_plan, assigned_room

def current_snapshot():
    config=db.session.get(PricingConfig,1)
    if config is None: raise CalculationError('Run flask init-db to seed the catalogue.')
    return {'captured_at':now().isoformat(),'catalogue':{m.id:m.as_dict() for m in db.session.scalars(db.select(Material))},'pricing':deepcopy(config.values)}

def recalculate_item(item, snapshot):
    try:
        item.result=calculate(item.type,item.subtype,item.inputs,item.options,snapshot['catalogue'],snapshot['pricing']['kerf'],item.id)
        groups=item.result['groups']
        slat=sum(sum(c['length_mm'] for c in g['cuts']) for k,g in groups.items() if snapshot['catalogue'][g['material_id']]['category']=='mdf' and k!='ledge')/1000
        finish=sum(sum(c['length_mm'] for c in g['cuts']) for k,g in groups.items() if snapshot['catalogue'][g['material_id']]['category']=='bead' or k=='ledge')/1000
        dado=sum(sum(c['length_mm'] for c in g['cuts']) for g in groups.values() if snapshot['catalogue'][g['material_id']]['category']=='dado')/1000
        item.pricing_result={'required_panelling_m':slat,'required_finish_m':finish+dado,'required_dado_m':dado,'labour_cost':money(slat*snapshot['pricing']['mdf_slat_per_m_gbp']+finish*snapshot['pricing']['bead_per_m_gbp']+dado*snapshot['pricing']['dado_per_m_gbp'])}
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
    state = {row.material_id: row for row in quote.material_states}
    purchases = {}
    assigned_purchases = {}
    for row in quote.purchases:
        purchases[row.material_id] = purchases.get(row.material_id, 0) + row.quantity
        if assigned_room(quote, row) is not None:
            assigned_purchases[row.material_id] = assigned_purchases.get(row.material_id, 0) + row.quantity
    rows = db.session.scalars(db.select(OwnedStockAllocation).where(OwnedStockAllocation.quote_id == quote.id)).all()
    physical = procurement_plan(quote, result)
    room_needs, unused_full = physical if physical is not None else (None, None)
    normal = {row['material_id']: row for row in result.get('materials', [])
              if not row.get('is_calculated_consumable')}
    needed_ids = {material_id for _, material_id in room_needs} if room_needs is not None else set()
    material_ids = list(normal) + sorted((needed_ids | set(state)) - set(normal))
    plan = []
    for material_id in material_ids:
        calculated = normal.get(material_id)
        # Mastic is calculated from installed work, rather than a catalogue
        # stock product. It is appended below so it follows the same
        # outstanding-procurement display path without entering stock packing.
        extra = state.get(material_id).extra_quantity if material_id in state else 0
        calculated_units = int(calculated['new_purchase_units']) if calculated else 0
        total = calculated_units + extra
        material_allocations = [row for row in rows if row.material_id == material_id
                                and assigned_room(quote, row) is not None]
        allocated = sum(row.quantity for row in material_allocations)
        purchased = purchases.get(material_id, 0)
        product = quote.snapshot['catalogue'].get(material_id, {})
        if room_needs is None:
            gross_need = (procurement_units(quote, calculated, extra, material_allocations)
                          if calculated else max(0, extra - allocated))
            need = max(0, gross_need - assigned_purchases.get(material_id, 0))
            room_purchase_units = []
            extra_need = 0
        else:
            room_purchase_units = [dict(room_id=room.id, room_name=room.name,
                                        units=room_needs[(room.id, material_id)])
                                   for room in quote.rooms if room_needs[(room.id, material_id)]]
            extra_need = max(0, extra - unused_full[material_id])
            need = sum(room['units'] for room in room_purchase_units) + extra_need
        row = dict(calculated) if calculated else dict(
            material_id=material_id, label=product['label'], category=product['category'],
            new_purchase_units=0, cost=0, room_demands=[])
        row.update(calculated_quantity=calculated_units, extra_quantity=extra,
                   total_quantity=total, allocated_owned_quantity=allocated,
                   purchased_quantity=purchased, need_to_purchase_quantity=need,
                   room_purchase_units=room_purchase_units, extra_need_units=extra_need,
                   unit_price=product.get('price', 0),
                   chargeable_cost=money((calculated['cost'] if calculated else 0) +
                                         extra * product.get('price', 0)))
        plan.append(row)
    mastic_units = int(result.get('mastic_units', 0) or 0)
    if mastic_units:
        mastic_cost = money(result.get('mastic_cost', 0))
        plan.append(dict(material_id='calculated-mastic', label='Mastic',
                         category='consumable', is_calculated_consumable=True,
                         calculated_quantity=mastic_units, extra_quantity=0,
                         total_quantity=mastic_units, allocated_owned_quantity=0,
                         purchased_quantity=0, need_to_purchase_quantity=mastic_units,
                         unit_price=money(mastic_cost / mastic_units),
                         chargeable_cost=mastic_cost))
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
    from ..calculations.dado import SUPPORTED_DADO_STYLES
    if any(i.type.startswith('DADO_') and i.subtype not in SUPPORTED_DADO_STYLES for r in quote.rooms for i in r.items):
        raise CalculationError('A saved quote contains a dado style coming later. Its snapshot and results are retained. Explicitly resolve that item before refreshing prices.')
    quote.snapshot=current_snapshot()
    for room in quote.rooms:
        for item in room.items: recalculate_item(item,quote.snapshot)
    reaggregate(quote)
