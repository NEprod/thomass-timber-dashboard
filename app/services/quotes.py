from copy import deepcopy
from ..models import db, Material, PricingConfig, Quote, now
from ..calculations.sections import calculate
from ..calculations.packing import CalculationError
from ..calculations.pricing import aggregate, money

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

def reaggregate(quote):
    quote.result=aggregate([i.result for r in quote.rooms for i in r.items],quote.snapshot['catalogue'],quote.snapshot['pricing'],quote.full_days,quote.extra_hours)
    quote.updated_at=now()


def refresh_prices(quote):
    from ..calculations.dado import SUPPORTED_DADO_STYLES
    if any(i.type.startswith('DADO_') and i.subtype not in SUPPORTED_DADO_STYLES for r in quote.rooms for i in r.items):
        raise CalculationError('A saved quote contains a dado style coming later. Its snapshot and results are retained. Explicitly resolve that item before refreshing prices.')
    quote.snapshot=current_snapshot()
    for room in quote.rooms:
        for item in room.items: recalculate_item(item,quote.snapshot)
    reaggregate(quote)
