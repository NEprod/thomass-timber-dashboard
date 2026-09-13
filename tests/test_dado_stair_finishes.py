"""New calculation regressions, not physical stair/saw validation."""
from copy import deepcopy
import pytest
from app.calculations.sections import calculate, DADO_STYLES
from app.calculations.pricing import aggregate
from app.calculations.packing import CalculationError
from app.calculations.stair_bead import bead_edges
from app.calculations.geometry import stair_geometry
from test_calculations import STAIR, OPTIONS


def dado(catalogue, length=4800, style='Dado', kerf=3, **inputs):
    return calculate('DADO_STRAIGHT', style, dict(wall_length=length, gap_width=100,
        bottom_squares=4, top_squares=4, bottom_zone_height=1000,
        top_zone_height=1200, inner_inset=100, **inputs),
        {'dado_rail_id':'dado-45mm-3m','dado_square_id':'dado-45mm-3m'}, catalogue, kerf, 'dado-1')


def test_continuous_longest_same_profile_splitting_and_labels(catalogue):
    exact=dado(catalogue)
    group=next(iter(exact['groups'].values()))
    assert catalogue[group['material_id']]['length_mm']==4800
    assert catalogue[group['material_id']]['width_mm']==45
    assert len(group['cuts'])==1
    longer=dado(catalogue,6000)
    cuts=[c for g in longer['groups'].values() for c in g['cuts']]
    assert [c['length_mm'] for c in cuts]==[4800,1200]
    assert sum(len(g['strips']) for g in longer['groups'].values())==2
    assert len({c['join_id'] for c in cuts})==1
    assert all(c['work_item_id']=='dado-1' and 'segment' in c['label'] for c in cuts)
    assert sum(catalogue[g['material_id']]['length_mm']*len(g['strips']) for g in longer['groups'].values())==6300


@pytest.mark.parametrize('style',['Dado Squares Bottom'])
def test_gap_frames_and_explicit_nested_layout(catalogue,style):
    result=dado(catalogue,3000,style)
    frames=result['geometry']['frames']
    zones=2 if 'Top & Bottom' in style else 1
    layers=2 if 'Double' in style else 1
    assert len(frames)==4*zones*layers
    assert frames[0]['width_mm']==625 and frames[0]['height_mm']==800
    if layers==2:
        assert frames[1]['width_mm']==425 and frames[1]['height_mm']==600
    group=result['groups']['dado_dado-45mm-3m']
    square_cuts=[c for c in group['cuts'] if c['angle_information'].get('dado_role')=='square']
    assert len(square_cuts)==len(frames)*4
    assert all('square' in c['label'] and c['angle_information']['start_joint_setting']==45 for c in square_cuts)
    zero=dado(catalogue,3000,style,kerf=0)
    assert zero['geometry']==result['geometry']
    assert [c['length_mm'] for c in zero['groups']['dado_dado-45mm-3m']['cuts']]==[c['length_mm'] for c in group['cuts']]


def test_compatibility_and_invalid_demands(catalogue):
    products=deepcopy(catalogue)
    products['dado-45mm-3m']['uses']=['continuous_dado']
    with pytest.raises(CalculationError,match='configured profile'):
        dado(products,3000,'Dado Squares Bottom')
    for product in products.values():
        if product['category']=='dado': product['length_mm']=0
    with pytest.raises(CalculationError): dado(products)
    with pytest.raises(CalculationError): dado(catalogue,-1)
    with pytest.raises(CalculationError): dado(catalogue,200,'Dado Squares Bottom')
    inputs=dict(wall_length=3000,gap_width=100,bottom_squares=4,bottom_zone_height=1000,inner_inset=40)
    with pytest.raises(CalculationError,match='coming later'):
        calculate('DADO_STRAIGHT','Dado Double Squares Bottom',inputs,{'dado_rail_id':'dado-45mm-3m','dado_square_id':'dado-45mm-3m'},catalogue,3)


def test_quote_pools_identical_dado_stock_and_prices_installed_labour(catalogue,seed_data):
    first=dado(catalogue,2000);second=deepcopy(first)
    for group in second['groups'].values():
        for cut in group['cuts']:cut['work_item_id']='second'
    totals=aggregate([first,second],catalogue,seed_data['pricing'])
    row=totals['materials'][0]
    assert row['required_m']==4 and row['new_purchase_units']==2
    assert row['remainder_m']==.2 and row['kerf_loss_mm']==0
    assert row['cost']==2*catalogue[row['material_id']]['price']
    assert totals['labour_cost']==4*seed_data['pricing']['dado_per_m_gbp']
    assert {c['work_item_id'] for stock in row['stocks'] for c in stock['cuts']}=={'dado-1','second'}


def test_stair_dado_reuses_geometry_and_segment_boundaries(catalogue):
    inputs=dict(STAIR,gap_width=100)
    result=calculate('DADO_STAIR','Dado',inputs,{'dado_rail_id':'dado-45mm-3m'},catalogue,3)
    original=calculate('PANELLING_STAIR_HALF','plain',STAIR,OPTIONS,catalogue,3)
    assert all(result['geometry'][k]==original['geometry'][k] for k in ['horizontal_run','slope_angle','slope_mitre','top_angle_setting','bottom_angle_setting'])
    cuts=[c for g in result['groups'].values() for c in g['cuts']]
    by_role={c['role']:c for c in cuts}
    assert {k:c['length_mm'] for k,c in by_role.items()}=={'Lower landing dado':250,'Slope dado':1200,'Upper landing dado':250}
    assert by_role['Slope dado']['angle_information']['start_joint_setting']==16.78
    assert by_role['Slope dado']['angle_information']['end_joint_setting']==16.78
    assert all(c['allowance_mm']==0 for c in cuts)


def test_stair_bead_transition_provision_and_kerf(catalogue):
    bead=next(k for k,m in catalogue.items() if m['category']=='bead' and m['thickness_mm']==9)
    options=dict(OPTIONS,bead_id=bead,dado_enabled=True,dado_rail_id='dado-45mm-3m')
    results=[calculate('PANELLING_STAIR_HALF','ledge_bead',STAIR,options,catalogue,k) for k in (0,3)]
    a,b=[r['groups']['stair_opening_beads']['cuts'] for r in results]
    assert a==b and len(a)==20
    first=[c for c in a if c['angle_information']['square']==1]
    assert sorted(c['length_mm'] for c in first)==[120,120,180,180,960,960]
    assert all(c['angle_information']['stock_allowance'] for c in first)
    assert sum(c['length_mm'] for c in results[0]['groups']['ledge_beads']['cuts'])==1700
    assert (results[0]['horizontal_strips'],results[0]['vertical_strips'])==(2,3)
    g=stair_geometry(1500,1000,400,400,1000,1,1,100)
    edges=bead_edges(g,1500,400,400,100,1)
    assert len(edges)==8  # one opening crosses both aligned bends
    flat=stair_geometry(4000,1000,1500,1500,1200,4,1,100)
    edges=bead_edges(flat,4000,1500,1500,100,1)
    assert any('flat' in e['role'] for e in edges)
    assert all(e['length_mm'] in (875,800) for e in edges if 'flat' in e['role'])


def test_edit_new_finishes_persistence_snapshot_and_anchor(app,signed_in):
    from app.models import db, Quote, WorkItem, Material
    from test_application import create_quote, add_room, add_item, post_quote
    from test_calculations import HALF
    qid=create_quote(signed_in,app);rid=add_room(signed_in,app,qid,'Workshop comparison')
    stair=add_item(signed_in,app,qid,rid,'Synthetic stair','PANELLING_STAIR_HALF',STAIR)
    half=add_item(signed_in,app,qid,rid,'Half with rail','PANELLING_HALF',HALF)
    with app.app_context():
        unchanged=deepcopy(db.session.get(WorkItem,stair).result)
        snapshot=deepcopy(db.session.get(Quote,qid).snapshot)
    response=post_quote(signed_in,app,qid,'edit_item',room_id=rid,item_id=half,name='Half with rail',type='PANELLING_HALF',subtype='plain',mdf_id='mdf-9mm',dado_enabled='on',dado_rail_id='dado-45mm-3m',position=0,**HALF)
    assert response.location.endswith(f'#item-{half}')
    with app.app_context():
        item=db.session.get(WorkItem,half)
        assert item.result['valid'] and item.pricing_result['required_dado_m']==3
        assert db.session.get(WorkItem,stair).result==unchanged
        assert db.session.get(Quote,qid).snapshot==snapshot
        assert db.session.get(Quote,qid).result['required_dado_m']==3
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert f'id="item-cuts-{half}"' in page and 'stair-metrics' in page
    assert 'Top / bottom displayed settings' in page
    assert 'selected>45mm Dado 3m' in page
    response=post_quote(signed_in,app,qid,'edit_item',room_id=rid,item_id=half,name='Square dado',type='DADO_STRAIGHT',subtype='Dado Squares Bottom',wall_length=3000,gap_width=100,bottom_squares=4,bottom_zone_height=1000,dado_rail_id='dado-45mm-3m',dado_square_id='dado-45mm-3m',position=0)
    assert response.status_code==302
    with app.app_context():
        item=db.session.get(WorkItem,half)
        assert item.result['valid'] and item.result['geometry']['square_width']==625
        material=db.session.get(Material,'dado-45mm-3m')
        assert 'square_dado' in material.uses
        data=material.as_dict();data.update(material_id=material.id,active='on',edit_compatibility='1',uses=['square_dado'])
    assert signed_in.post('/materials',data=data).status_code==302
    with app.app_context():
        assert db.session.get(Material,'dado-45mm-3m').uses==['square_dado']
        assert db.session.get(Quote,qid).snapshot==snapshot
    assert signed_in.get(f'/quotes/{qid}').status_code==200
    post_quote(signed_in,app,qid,'edit_item',room_id=rid,item_id=half,name='Incomplete dado',type='DADO_STRAIGHT',subtype='Dado',wall_length='',dado_rail_id='dado-45mm-3m')
    with app.app_context():
        assert db.session.get(WorkItem,half).result['groups']=={}
        assert db.session.get(Quote,qid).result['final_price'] is None
        assert db.session.get(WorkItem,stair).result==unchanged


def test_existing_database_upgrade_preserves_prices(tmp_path):
    import json
    from flask_migrate import upgrade
    from sqlalchemy import text
    from app import create_app
    from app.models import db, Material
    app=create_app({'TESTING':True,'SECRET_KEY':'migration-only','SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'old.db')})
    with app.app_context():
        upgrade(revision='a29d1b65da4b')
        db.session.execute(text("INSERT INTO material (id,category,label,profile,length_mm,width_mm,thickness_mm,price,active,preferred_stock_mm) VALUES ('custom-id','dado','Edited label','45mm',3000,45,20,99,1,3000)"))
        db.session.commit()
        upgrade()
        row=db.session.get(Material,'custom-id')
        assert row.price==99 and row.label=='Edited label'
        assert row.uses==['continuous_dado','stair_dado','square_dado']


def test_stair_segment_splits_keep_only_external_mitres(catalogue):
    products=deepcopy(catalogue)
    for product in products.values():
        if product['category']=='dado' and product['profile']=='45mm':product['length_mm']=1000
    result=calculate('DADO_STAIR','Dado',dict(STAIR,gap_width=100),{'dado_rail_id':'dado-45mm-3m'},products,3)
    cuts=[c for g in result['groups'].values() for c in g['cuts'] if c['role']=='Slope dado']
    assert [c['length_mm'] for c in cuts]==[1000,200]
    assert [(c['angle_information']['start_joint_setting'],c['angle_information']['end_joint_setting']) for c in cuts]==[(16.78,0),(0,16.78)]
