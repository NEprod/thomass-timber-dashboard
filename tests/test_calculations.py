from copy import deepcopy
import math
import pytest
from app.calculations.sections import calculate
from app.calculations.geometry import stair_geometry
from app.calculations.packing import pack, split_run, CalculationError
from app.calculations.pricing import aggregate

FULL=dict(wall_length=3000,height=2400,horizontal_squares=4,vertical_squares=2,slat_width=100)
HALF=dict(FULL,height=1000,vertical_squares=1)
STAIR=dict(wall_length=1500,height=1000,lower_landing=250,upper_landing=250,slope_length=1200,horizontal_squares=4,vertical_squares=1,slat_width=100)
OPTIONS={'mdf_id':'mdf-9mm','ledge_width':18,'ledge_choice':'2x'}

def calc(catalogue,kind='FULL',inputs=None,subtype='plain',options=None):
    return calculate('PANELLING_'+kind,subtype,inputs or FULL,options or OPTIONS,catalogue,3,'wall-17')

def test_full_and_half_preserve_normal_geometry_and_counts(catalogue):
    full=calc(catalogue)
    assert full['geometry']=={'square_width':625,'square_height':1050}
    assert (full['horizontal_strips'],full['vertical_strips'])==(4,5)
    half=calc(catalogue,'HALF',HALF)
    assert half['geometry']=={'square_width':625,'square_height':800}
    assert (half['horizontal_strips'],half['vertical_strips'])==(3,2)
    multi=calc(catalogue,'HALF',dict(HALF,vertical_squares=2))
    assert len(multi['groups']['middle_horizontal']['cuts'])==4
    assert sum(c['length_mm'] for c in half['groups']['top_and_bottom_horizontal']['cuts'])==6000

def test_stair_golden_geometry():
    g=stair_geometry(1500,1000,250,250,1200,4,1,100)
    expected=dict(horizontal_run=1000,slope_angle=33.56,slope_mitre=16.78,square_width=250,square_height=800,
                  angled_square_width=300,angled_square_height=960,top_angle_setting=61.78,bottom_angle_setting=28.22)
    assert {k:g[k] for k in expected}==expected
    assert [c['type'] for c in g['columns']]==['transition','angled','angled','transition']
    assert g['counts']=={'flat':0,'angled':2,'transition':2}

def test_stair_golden_packing_labels_allowance(catalogue):
    result=calc(catalogue,'STAIR_HALF',STAIR)
    assert (result['horizontal_strips'],result['vertical_strips'])==(2,3)
    horizontal=result['groups']['top_and_bottom_horizontal']
    assert [[c['length_mm'] for c in s['cuts']] for s in horizontal['strips']]==[[1200,1200],[280,250,250,220]]
    cuts={c['role']:c for c in horizontal['cuts']}
    assert cuts['Top (Upper Landing)']['allowance_mm']==30
    assert cuts['Top (Lower Landing)']['allowance_mm']==-30
    assert cuts['Slope']['length_mm']==1200
    for strip in horizontal['strips']:
        for c in strip['cuts']:
            assert c['length_mm']==cuts[c['role']]['length_mm']
            assert c['work_item_id']=='wall-17'
            assert c['angle_information']['slope_mitre']==16.78
    short=calc(catalogue,'STAIR_HALF',dict(STAIR,lower_landing=20,slope_length=1500))
    top=[c for c in short['groups']['top_and_bottom_horizontal']['cuts'] if c['role']=='Top (Lower Landing)']
    assert top==[]  # historical clamp to zero, no zero-length purchase

def test_bead_ledge_and_stair_supported_boundary(catalogue):
    bead_id=next(k for k,m in catalogue.items() if m['category']=='bead' and m['thickness_mm']==9)
    options=dict(OPTIONS,bead_id=bead_id)
    for kind,inputs in [('FULL',FULL),('HALF',HALF)]:
        result=calc(catalogue,kind,inputs,'bead',options)
        cuts=result['groups']['square_beads']['cuts']
        assert len(cuts)==inputs['horizontal_squares']*inputs['vertical_squares']*4
    result=calc(catalogue,'HALF',HALF,'ledge_bead',options)
    assert sum(c['length_mm'] for c in result['groups']['ledge']['cuts'])==3000
    assert sum(c['length_mm'] for c in result['groups']['ledge_beads']['cuts'])==3000
    assert sum(len(g['strips']) for n,g in result['groups'].items() if 'bead' in n)==8
    with pytest.raises(CalculationError,match='unsupported'):
        calc(catalogue,'STAIR_HALF',STAIR,'bead',options)
    normal=calc(catalogue,'STAIR_HALF',dict(STAIR,lower_landing=0,upper_landing=0,slope_length=1800),'bead',options)
    assert len(normal['groups']['angled_square_beads']['cuts'])==16
    ledge=calc(catalogue,'STAIR_HALF',STAIR,'ledge')
    assert sum(c['length_mm'] for c in ledge['groups']['ledge']['cuts'])==1700

@pytest.mark.parametrize('key,value', [('horizontal_squares',0),('vertical_squares',1.2),('height',-1),('wall_length',''),('slat_width',2000),('height','nan'),('wall_length','inf'),('horizontal_squares',101)])
def test_bad_measurements_fail(catalogue,key,value):
    with pytest.raises(CalculationError):calc(catalogue,inputs=dict(FULL,**{key:value}))

def test_slope_and_stock_validation(catalogue):
    with pytest.raises(CalculationError,match='Slope'):calc(catalogue,'STAIR_HALF',dict(STAIR,slope_length=900))
    for changes in [{'length_mm':0},{'width_mm':90},{'length_mm':1000}]:
        products=deepcopy(catalogue);products['mdf-9mm'].update(changes)
        with pytest.raises(CalculationError):calc(products)
    with pytest.raises(CalculationError):calc(catalogue,options=dict(OPTIONS,ledge_width=5000),kind='HALF',inputs=HALF,subtype='ledge')

def test_kerf_contract_and_bounded_packing():
    cuts=[{'length_mm':500,'label':'first'},{'length_mm':497,'label':'second'}]
    strips=pack(cuts,1000,3)
    assert len(strips)==1  # isolated correction: legacy produced two
    assert strips[0]['used_mm']==1000 and strips[0]['kerf_loss_mm']==3
    assert strips[0]['remainder_mm']==0
    assert [c['label'] for c in strips[0]['cuts']]==['first','second']
    assert pack(cuts,1000,3)==strips
    assert len(pack([{'length_mm':500},{'length_mm':500}],1000,0))==1
    for stock,kerf in [(0,3),(-1,3),(1000,-1),(1000,5000)]:
        with pytest.raises(CalculationError):pack(cuts,stock,kerf)
    with pytest.raises(CalculationError):pack([{'length_mm':3500}],3000,3)
    with pytest.raises(CalculationError):pack([{'length_mm':0}],3000,3)
    assert sum(split_run(6001,2440))==6001
    assert max(split_run(6001,2440))<=2440

def test_real_demand_purchasing_pricing(catalogue,seed_data):
    config=seed_data['pricing']
    result=calc(catalogue)
    total=aggregate([result],catalogue,config)
    row=total['materials'][0]
    assert row['required_m']==19.5  # 5×2400 + 12×625, no purchased waste
    assert row['purchased_strip_m']==21.96
    assert row['new_purchase_units']==1
    assert row['cost']==catalogue['mdf-9mm']['price']
    assert row['allocated_existing_mm']==0
    assert total['labour_cost']==round(19.5*config['mdf_slat_per_m_gbp'],2)
    assert total['mastic_units']==math.ceil(19.5/config['mastic_linear_coverage']*1.5)
    assert total['final_price']==math.ceil((total['material_cost']+total['take_home'])/10)*10
    timed=aggregate([result],catalogue,config,days=3,hours=2)
    assert timed['take_home']==3*config['day_rate']+2*config['hourly_rate']
    doubled=aggregate([result,result],catalogue,config)
    assert doubled['materials'][0]['required_m']==39
    assert doubled['materials'][0]['new_purchase_units']==2
    empty=aggregate([],catalogue,config,days=3)
    assert all(empty[k]==0 for k in ['material_cost','delivery_cost','cut_cost','mastic_cost','final_price','take_home'])
    invalid=aggregate([result,{'valid':False}],catalogue,config)
    assert invalid['final_price'] is None and not invalid['valid']
