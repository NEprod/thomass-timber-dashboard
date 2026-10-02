from copy import deepcopy
import math
from xml.etree import ElementTree as ET

import pytest

from app.calculations.sections import calculate
from app.calculations.pricing import aggregate
from app.services.wall_plans import render_wall_plan
from app.services.installed_dimensions import installed_groups
from app.models import db, Quote
from test_application import create_quote, add_room, add_item, post_quote
from test_calculations import OPTIONS, STAIR
from test_wall_plans import REPRESENTATIVE_STAIR, boundary_y


def stair(catalogue, values=None, bead=True):
    return calculate('PANELLING_STAIR_HALF','bead' if bead else 'plain',values or REPRESENTATIVE_STAIR,
        dict(OPTIONS,bead_id='bead-glass_bead-9x9'),catalogue,3,'1')


def components(result):return result['geometry']['wall_layout']['installed_components']


def test_normal_sloped_opening_exact_vertices_edges_angles_and_svg(catalogue):
    result=stair(catalogue);plan=result['geometry']['wall_layout']
    opening=next(p for p in components(result) if p['label']=='Opening 2.1')
    assert opening['status']=='EXACT'
    element=plan['elements'][opening['element_index']];points=element['points'];m=opening['measurements']
    for i,(x,y) in enumerate(points):
        boundary=plan['boundaries']['bottom_inner' if i<2 else 'top_inner']
        assert y==pytest.approx(boundary_y(boundary,x))
    assert m['opening']['left_vertical_mm']==pytest.approx(680)
    assert m['opening']['right_vertical_mm']==pytest.approx(680)
    assert m['opening']['horizontal_spacing_mm']==1000
    assert m['opening']['top_edges_mm']==pytest.approx([1600])
    assert m['opening']['bottom_edges_mm']==pytest.approx([1600])
    assert sorted(a['internal_angle_deg'] for a in m['angles'])==pytest.approx([38.68218745]*2+[141.31781255]*2)
    for edge in m['edges']:
        assert edge['length_mm']==pytest.approx(math.dist(points[edge['start_index']],points[edge['end_index']]))
    assert opening['prepare_dimensions'] is None  # Old approximations are not cutting truth.
    root=ET.fromstring(render_wall_plan(plan,'Stair'))
    polygon=next(e for e in root.iter() if e.attrib.get('data-kind')=='opening' and e.find('{http://www.w3.org/2000/svg}title').text==element['label'])
    rendered=[list(map(float,p.split(','))) for p in polygon.attrib['points'].split()]
    for a,b in zip(rendered,points):assert a==pytest.approx(b,abs=.01)


def test_batten_mitred_point_references_derived_from_intersections(catalogue):
    result=stair(catalogue)
    batten=next(p for p in components(result) if p['label']=='Vertical batten 3')
    points=result['geometry']['wall_layout']['elements'][batten['element_index']]['points']
    m=batten['measurements']['member']
    assert m['centreline_mm']==pytest.approx(680)
    assert m['long_point_mm']==pytest.approx(max(y for x,y in points)-min(y for x,y in points))
    assert m['short_point_mm']==pytest.approx(min(points[2][1],points[3][1])-max(points[0][1],points[1][1]))
    assert m['start_mitre_deg']==pytest.approx(result['geometry']['slope_angle'],abs=.01)
    assert m['longitudinal_edges_mm']==pytest.approx([680,680])
    assert batten['base_cut_length_mm']==pytest.approx(m['long_point_mm'],abs=1e-6)
    assert batten['base_cut_length_mm']==pytest.approx(804.89996)
    assert 'projected along the member axis' in m['reference']


@pytest.mark.parametrize('slope',[3500,4000])
def test_slope_landing_rail_measurements_mitres_exact_base_cuts(catalogue,slope):
    result=stair(catalogue,dict(REPRESENTATIVE_STAIR,slope_length=slope));g=result['geometry']
    rails={p['label']:p for p in components(result) if p['component']=='Rail'}
    for name in ('Top','Bottom'):
        rail=rails[name+' rail · Slope'];m=rail['measurements']['member']
        assert rail['status']=='EXACT' and rail['base_cut_length_mm']==pytest.approx(m['long_point_mm'],abs=1e-6)
        assert m['centreline_mm']==pytest.approx(slope)
        assert m['longitudinal_edges_mm']==pytest.approx([slope,slope])
        assert m['start_mitre_deg']==pytest.approx(g['slope_mitre'],abs=.01)
        assert m['end_mitre_deg']==pytest.approx(g['slope_mitre'],abs=.01)
        assert m['long_point_mm']>=m['centreline_mm']>=m['short_point_mm']
    assert rails['Top rail · Lower landing']['base_cut_length_mm']==pytest.approx(rails['Top rail · Lower landing']['measurements']['member']['long_point_mm'],abs=1e-6)
    assert rails['Top rail · Upper landing']['base_cut_length_mm']==1000
    assert rails['Bottom rail · Lower landing']['prepare_length_mm']==1000
    # Historical landing tolerances are replaced by physical long points.
    assert rails['Top rail · Lower landing']['measurements']['member']['long_point_mm']>1000


def test_each_six_piece_transition_audited_without_fake_installed_bead_sizes(catalogue):
    result=stair(catalogue);plan=result['geometry']['wall_layout']
    openings=[p for p in components(result) if p['component']=='Panel opening']
    assert len(openings)==4 and all(p['status']=='EXACT' for p in openings)
    for number in (1,4):
        opening=next(p for p in openings if p['label']==f'Opening {number}.1')
        assert len(opening['measurements']['edges'])==6
        points=plan['elements'][opening['element_index']]['points'];half=len(points)//2
        for index,(x,y) in enumerate(points):
            assert y==pytest.approx(boundary_y(plan['boundaries']['bottom_inner' if index<half else 'top_inner'],x))
        pieces=[p for p in components(result) if p['component']=='Bead / moulding' and f'square {number} row' in p['label']]
        assert len(pieces)==6
        assert all(p['status']=='EXACT' and p['cut_status']=='EXACT' for p in pieces)
        assert all(p['base_cut_length_mm']==pytest.approx(p['measurements']['member']['long_point_mm'],abs=1e-6) for p in pieces)
    assert sum(e['kind']=='bead' for e in plan['elements'])==20
    assert all(not e['provisional'] for e in plan['elements'])
    svg=render_wall_plan(plan,'Stair')
    assert 'Trim to fit' not in svg and 'stroke-dasharray' not in svg


def test_normal_bead_reference_paths_match_installed_opening(catalogue):
    result=stair(catalogue);plan=result['geometry']['wall_layout']
    pieces=[p for p in components(result) if p['component']=='Bead / moulding' and 'square 2 row' in p['label']]
    assert len(pieces)==4 and all(p['status']=='EXACT' for p in pieces)
    opening=next(e for e in plan['elements'] if e['kind']=='opening' and e['label'].startswith('Opening 2.1'))
    edges=[(a,b) for a,b in zip(opening['points'],opening['points'][1:]+opening['points'][:1])]
    for p in pieces:
        a,b=p['vertices'][:2]
        assert (a,b) in edges
        m=p['measurements']['member']
        assert m['long_point_mm']>=m['centreline_mm']>=m['short_point_mm']


def test_dado_installed_centreline_path_and_existing_mitres(catalogue):
    result=calculate('DADO_STAIR','Dado',dict(REPRESENTATIVE_STAIR,dado_height=1100),
        dict(dado_rail_id='dado-45mm-3m'),catalogue,3,'2')
    plan=result['geometry']['wall_layout'];rows=plan['installed_components']
    assert len(rows)==3
    slope=next(p for p in rows if p['label']=='Slope dado')
    assert slope['status']=='EXACT' and slope['base_cut_length_mm']==pytest.approx(4021.617301)
    m=slope['measurements']['member'];points=slope['vertices']
    assert m['centreline_mm']==pytest.approx(4000)
    assert m['long_point_mm']==pytest.approx(4021.617301)
    assert m['short_point_mm']==pytest.approx(3978.382699)
    assert [m['start_mitre_deg'],m['end_mitre_deg']]==pytest.approx([25.66,25.66],abs=.01)
    # The known width produces parallel physical edges sharing exact seams.
    assert math.dist(points[0],points[1])==pytest.approx(4000)


def test_additional_dado_physical_cut_does_not_depend_on_absolute_height(catalogue):
    result=calculate('PANELLING_STAIR_HALF','plain',REPRESENTATIVE_STAIR,
        dict(OPTIONS,dado_enabled=True,dado_rail_id='dado-45mm-3m'),catalogue,3)
    rows=[p for p in components(result) if p['component']=='Dado']
    assert len(rows)==3 and all(p['status']=='EXACT' and p['base_cut_length_mm']>0 for p in rows)


def test_orientation_render_only_and_grouping_does_not_mutate_materials(catalogue,seed_data):
    right=stair(catalogue);before=deepcopy(right)
    left=calculate('PANELLING_STAIR_HALF','bead',REPRESENTATIVE_STAIR,
        dict(OPTIONS,bead_id='bead-glass_bead-9x9',high_end='Left'),catalogue,3,'1')
    assert left==right
    plan=right['geometry']['wall_layout']
    groups=installed_groups(plan)
    assert any(p['quantity']==3 and p['component']=='Vertical batten' for p in groups)
    svg=render_wall_plan(plan,'Stair','Left')
    assert 'translate(4500 0) scale(-1 1)' in svg
    assert aggregate([left],catalogue,seed_data['pricing'])==aggregate([right],catalogue,seed_data['pricing'])
    assert right==before


def test_current_quote_installed_detail_and_prepare_summary_reopen(app,signed_in):
    qid=create_quote(signed_in,app);rid=add_room(signed_in,app,qid,'Installed room')
    iid=add_item(signed_in,app,qid,rid,'Stair','PANELLING_STAIR_HALF',REPRESENTATIVE_STAIR)
    assert post_quote(signed_in,app,qid,'edit_item',room_id=rid,item_id=iid,name='Stair',type='PANELLING_STAIR_HALF',subtype='bead',position=0,
        mdf_id='mdf-9mm',bead_id='bead-glass_bead-9x9',**REPRESENTATIVE_STAIR).status_code==302
    with app.app_context():before=deepcopy(db.session.get(Quote,qid).result)
    for _ in range(2):
        page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
        assert 'Installed Dimensions' in page and 'Installed vertical sides' in page
        assert '680.00 / 680.00 mm' in page and '1600.00 mm' in page
        assert 'Installed long point' in page and 'Base cut: 804.90 mm' in page
        assert 'Physical cut: PROVISIONAL' not in page and 'Installed: site-fit' not in page
        assert 'Cut Summary' in page and '2 × 804.9mm' in page
        assert 'Base cut: 952.36 mm' in page and 'Site-fit Prepare: 1280 mm' not in page
        assert 'stair transitions are labelled trim-to-fit provisions' not in page
    with app.app_context():assert db.session.get(Quote,qid).result==before


def test_representative_landing_and_slope_base_cut_deltas(catalogue):
    result=stair(catalogue,bead=False)
    rows={p['label']:p for p in components(result)}
    expected={
        'Top rail · Lower landing':(1048.038446,1000,1024.019223),
        'Top rail · Upper landing':(1000,951.961554,975.980777),
        'Bottom rail · Lower landing':(1000,951.961554,975.980777),
        'Bottom rail · Upper landing':(1048.038446,1000,1024.019223),
        'Top rail · Slope':(4048.038446,3951.961554,4000),
        'Bottom rail · Slope':(4048.038446,3951.961554,4000)}
    cuts={c['id']:c for g in result['groups'].values() for c in g['cuts']}
    owners=[]
    for label,(long,short,centre) in expected.items():
        p=rows[label];m=p['measurements']['member']
        assert (m['long_point_mm'],m['short_point_mm'],m['centreline_mm'])==pytest.approx((long,short,centre),abs=1e-6)
        assert p['base_cut_length_mm']==pytest.approx(long,abs=1e-6)
        assert sum(cuts[cid]['length_mm'] for cid in p['cut_ids'])==pytest.approx(long,abs=1e-6)
        assert all(cuts[cid]['allowance_mm']==0 and cuts[cid]['requirement_status']=='EXACT' for cid in p['cut_ids'])
        owners.extend(p['cut_ids'])
    assert len(owners)==len(set(owners))


def test_transition_reference_exactness_does_not_overclaim_physical_bead_cut(catalogue):
    r=stair(catalogue)
    for n in (1,4):
        pieces=[p for p in components(r) if p['component']=='Bead / moulding' and f'square {n} row' in p['label']]
        assert len(pieces)==6
        assert sum(p['status']=='EXACT' for p in pieces)==6
        assert all(p['cut_status']=='EXACT' and p['base_cut_length_mm']>0 for p in pieces)
        assert all(c['requirement_status']=='EXACT' and 'stock_allowance' not in c['angle_information'] for c in r['groups']['stair_opening_beads']['cuts'])


def test_exact_room_demand_repacked_without_spares_and_charge_follows_stock(catalogue,seed_data):
    r=stair(catalogue,bead=False)
    rooms=[dict(id=1,name='Room',items=[dict(id='1',name='Stair',result=r)])]
    priced=aggregate([r],catalogue,seed_data['pricing'],rooms=rooms)
    stocks=[s for s in priced['room_stocks'] if s['category']=='mdf']
    assert len(stocks)==1 and sum(len(s['cuts']) for s in stocks)==7
    assert stocks[0]['remainder_mm']==502  # Seven rips, six 3mm kerfs.
    # Approved prepared-strip pricing: seven actual rips, not nine legacy estimates.
    assert priced['total_prepared_strips']==7 and priced['cut_cost']==14
    assert priced['stock_material_cost']==18 and priced['material_cost']==50.7
    seen=[]
    for stock in stocks:
        for rip in stock['cuts']:
            cuts=rip['finished_cuts']
            used=sum(c['length_mm'] for c in cuts)+3*(len(cuts)-1)
            assert used<=stock['stock_length_mm']+1e-6
            assert rip['used_length_mm']==pytest.approx(used,abs=1e-6)
            seen.extend(c['id'] for c in cuts)
    required=[c['id'] for group in r['groups'].values() for c in group['cuts']]
    assert sorted(seen)==sorted(required)
    assert aggregate([r],catalogue,seed_data['pricing'],rooms=rooms)==priced
    # Adding an independently owned room reproduces demand without cross pooling.
    two=aggregate([r,r],catalogue,seed_data['pricing'],rooms=rooms+[dict(rooms[0],id=2)])
    assert len(two['room_stocks'])==2 and two['stock_material_cost']==36


def test_intermediate_exact_members_and_bend_members_distinguished(catalogue):
    r=stair(catalogue,dict(REPRESENTATIVE_STAIR,vertical_squares=2),bead=False)
    members=[p for p in components(r) if p['component']=='Middle rail']
    assert len(members)==4
    assert sum(p['cut_status']=='EXACT' for p in members)==2
    for p in members:
        if p['cut_status']=='EXACT':
            assert p['base_cut_length_mm']==pytest.approx(p['measurements']['member']['long_point_mm'],abs=1e-6)
        else:assert 'base_cut_length_mm' not in p and 'crosses a bend' in p['reason']


@pytest.mark.parametrize('square',[1,4])
def test_transition_profiles_share_exact_width_aware_mitre_seams(catalogue,square):
    result=stair(catalogue)
    rows=[p for p in components(result) if p['component']=='Bead / moulding' and f'square {square} row' in p['label']]
    assert len(rows)==6
    # All neighbouring outside endpoints and inset endpoints identify exactly
    # the same seam, including the concave landing-to-slope mitre.
    for p in rows:
        a,b,c,d=p['vertices']
        length=math.dist(a,b);axis=((b[0]-a[0])/length,(b[1]-a[1])/length)
        for inner in (c,d):
            distance=abs((inner[0]-a[0])*axis[1]-(inner[1]-a[1])*axis[0])
            assert distance==pytest.approx(9)
        for outer,inner in ((a,d),(b,c)):
            neighbours=[q for q in rows if q is not p and any(math.dist(v,outer)<1e-7 for v in q['vertices'][:2])]
            assert len(neighbours)==1
            other=neighbours[0]['vertices']
            assert any(math.dist(v,inner)<1e-7 for v in other[2:])
        m=p['measurements']['member']
        projections=[x*axis[0]+y*axis[1] for x,y in p['vertices']]
        assert m['long_point_mm']==pytest.approx(max(projections)-min(projections))
        assert m['long_point_mm']>m['short_point_mm']
        assert p['base_cut_length_mm']==pytest.approx(m['long_point_mm'],abs=1e-6)
        if 'segment' in p['label']:
            assert any(angle==pytest.approx(result['geometry']['slope_mitre'],abs=.01)
                for angle in (m['start_mitre_deg'],m['end_mitre_deg']))
        assert p['previous_prepare_length_mm'] in (1440,160,1280)


def test_profile_svg_and_stock_use_the_same_exact_physical_members(catalogue,seed_data):
    r=stair(catalogue);plan=r['geometry']['wall_layout']
    rows=[p for p in components(r) if p['component']=='Bead / moulding']
    elements={e['label']:e for e in plan['elements'] if e['kind']=='bead'}
    cuts={c['id']:c for c in r['groups']['stair_opening_beads']['cuts']}
    assert len(rows)==len(elements)==len(cuts)==20
    for p in rows:
        assert elements[p['label']]['points']==p['vertices']
        assert not elements[p['label']]['provisional']
        assert sum(cuts[cid]['length_mm'] for cid in p['cut_ids'])==p['base_cut_length_mm']
        assert all(cuts[cid]['allowance_mm']==0 and 'trim-to-fit' not in cuts[cid]['label'] for cid in p['cut_ids'])
    priced=aggregate([r],catalogue,seed_data['pricing'],rooms=[dict(id=1,name='Room',items=[dict(id='1',name='Stair',result=r)])])
    stocks=[s for s in priced['room_stocks'] if s['category']=='bead']
    assigned=[c for stock in stocks for c in stock['cuts']]
    assert sorted(c['id'] for c in assigned)==sorted(cuts)
    for stock in stocks:
        assert sum(c['length_mm'] for c in stock['cuts'])+stock['kerf_loss_mm']+stock['remainder_mm']==pytest.approx(stock['stock_length_mm'],abs=1e-6)
    assert len(stocks)==7


def test_dado_square_transition_profiles_use_known_width_and_exact_edges(catalogue):
    inputs=dict(REPRESENTATIVE_STAIR,gap_width=100,bottom_squares=4,bottom_zone_height=1000)
    options=dict(dado_rail_id='dado-45mm-3m',dado_square_id='dado-astragal-21x8mm')
    r=calculate('DADO_STAIR','Dado Squares Bottom',inputs,options,catalogue,3)
    plan=r['geometry']['wall_layout'];rows=[p for p in components(r) if p['component']=='Dado square profile']
    frames={e['label']:e for e in plan['elements'] if e['kind']=='frame'}
    assert len(rows)==len(frames)==20
    for p in rows:
        a,b,c,d=p['vertices'];axis=((b[0]-a[0])/math.dist(a,b),(b[1]-a[1])/math.dist(a,b))
        assert abs((d[0]-a[0])*axis[1]-(d[1]-a[1])*axis[0])==pytest.approx(21)
        assert p['status']==p['cut_status']=='EXACT'
        assert p['base_cut_length_mm']==pytest.approx(p['measurements']['member']['long_point_mm'],abs=1e-6)
        assert frames[p['label']]['points']==p['vertices']
        assert p['measurements']['member']['short_point_mm']>0
        same_opening=[q for q in rows if q['information']['square']==p['information']['square']]
        for outer,inner in ((a,d),(b,c)):
            neighbour=next(q for q in same_opening if q is not p and any(math.dist(v,outer)<1e-7 for v in q['vertices'][:2]))
            assert any(math.dist(v,inner)<1e-7 for v in neighbour['vertices'][2:])
        # Non-adjacent inset edges must not cross. This independently checks
        # physical fit, rather than treating a positive cut length as proof.
        def side(x,y,z):return (y[0]-x[0])*(z[1]-x[1])-(y[1]-x[1])*(z[0]-x[0])
        for q in same_opening:
            x,y=q['vertices'][2:]
            if any(math.dist(u,v)<1e-7 for u in (c,d) for v in (x,y)):continue
            assert not (side(c,d,x)*side(c,d,y)<0 and side(x,y,c)*side(x,y,d)<0)
    left=calculate('DADO_STAIR','Dado Squares Bottom',inputs,dict(options,high_end='Left'),catalogue,3)
    assert left==r
    assert 'stroke-dasharray' not in render_wall_plan(plan,'Dado')
    from app.calculations.packing import CalculationError
    with pytest.raises(CalculationError,match='45mm profile cannot fit'):
        calculate('DADO_STAIR','Dado Squares Bottom',inputs,dict(options,dado_square_id='dado-45mm-3m'),catalogue,3)


def test_missing_profile_width_stops_instead_of_fabricating_long_points(catalogue):
    from app.calculations.packing import CalculationError
    products=deepcopy(catalogue)
    products['bead-glass_bead-9x9']['width_mm']=None
    with pytest.raises(CalculationError,match='profile width'):
        stair(products)
