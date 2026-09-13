"""Historical pricing policy with explicit installed/purchase quantities."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import math
from .packing import pack, number

def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))

def aggregate(results, catalogue, config, days=0, hours=0):
    days=number(days,'Full days',allow_zero=True,maximum=365)
    hours=number(hours,'Extra hours',allow_zero=True,maximum=10000)
    materials={}; rip_demands=defaultdict(list)
    installed_slat=installed_finish=0
    for result in results:
        if not result.get('valid'): continue
        for name,group in result['groups'].items():
            product=catalogue[group['material_id']]
            row=materials.setdefault(group['material_id'],dict(material_id=product['id'],label=product['label'],category=product['category'],required_mm=0,allocated_existing_mm=0,new_purchase_units=0,strip_stock_mm=0,kerf_loss_mm=0))
            required=sum(c['length_mm'] for c in group['cuts'])
            row['required_mm']+=required
            row['strip_stock_mm']+=len(group['strips'])*product['length_mm']
            row['kerf_loss_mm']+=sum(x['kerf_loss_mm'] for x in group['strips'])
            if product['category']=='mdf':
                for strip in group['strips']:
                    rip_demands[group['material_id']].append({'length_mm':group['width_mm'],'label':'Ledge rip' if name=='ledge' else 'Slat rip','role':name,'work_item_id':strip['cuts'][0]['work_item_id']})
                if name=='ledge': installed_finish+=required
                else: installed_slat+=required
            else:
                row['new_purchase_units']+=len(group['strips']);installed_finish+=required
    cost=0; total_rips=0
    for key,row in materials.items():
        product=catalogue[key]
        if product['category']=='mdf':
            # Historical slat-first ripping, with one bounded packing representation.
            demand=sorted(rip_demands[key],key=lambda d:d['role']=='ledge')
            row['boards']=pack(demand,product['width_mm'],config['kerf'],descending=False)
            row['new_purchase_units']=len(row['boards']);total_rips+=len(demand)
            row['purchased_area_m2']=row['new_purchase_units']*product['length_mm']*product['width_mm']/1e6
            row['rip_remainder_area_m2']=sum(b['remainder_mm'] for b in row['boards'])*product['length_mm']/1e6
        row['required_m']=round(row.pop('required_mm')/1000,6)
        row['purchased_strip_m']=round(row['strip_stock_mm']/1000,6)
        row['remainder_m']=round((row['strip_stock_mm']-row['required_m']*1000-row['kerf_loss_mm'])/1000,6)
        row['cost']=money(row['new_purchase_units']*product['price']);cost+=row['cost']
    has_work=bool(materials)
    slat_m,finish_m=installed_slat/1000,installed_finish/1000
    mastic=math.ceil((slat_m+finish_m)/config['mastic_linear_coverage']*1.5) if has_work else 0
    mastic_cost=money(mastic*config['mastic_unit_price'])
    cut_cost=money((total_rips+1)*config['cut_cost_per_strip']) if total_rips else 0
    delivery=config['delivery_cost'] if has_work else 0
    material_cost=money(cost+mastic_cost+cut_cost+delivery)
    labour=money(slat_m*config['mdf_slat_per_m_gbp']+finish_m*config['bead_per_m_gbp'])
    time_allowance=money(days*config['day_rate']+hours*config['hourly_rate']) if has_work else 0
    take_home=max(labour,time_allowance)
    valid=all(r.get('valid') for r in results)
    return dict(valid=valid,materials=list(materials.values()),required_panelling_m=round(slat_m,6),required_finish_m=round(finish_m,6),
                stock_material_cost=money(cost),mastic_units=mastic,mastic_cost=mastic_cost,cut_cost=cut_cost,delivery_cost=delivery,
                material_cost=material_cost,labour_cost=labour,time_allowance=time_allowance,take_home=take_home,
                final_price=math.ceil(money(material_cost+take_home)/10)*10 if valid else None)
