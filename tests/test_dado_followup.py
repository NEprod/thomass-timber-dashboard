from copy import deepcopy
import pytest
from app.calculations.sections import calculate,DADO_STYLES
from app.calculations.dado import dado_summary
from app.calculations.pricing import aggregate
from app.calculations.packing import CalculationError
from app.calculations.geometry import stair_route_geometry,stair_geometry

@pytest.fixture
def stocks(catalogue):
    products={k:deepcopy(v) for k,v in catalogue.items() if v['category']!='dado' or v['profile']!='45mm'}
    template=catalogue['dado-45mm-3m']
    for length in (1000,2400,3000,4800):
        p=dict(template,id=f'rail-{length}',label=f'45 mm {length}',length_mm=length,price=length/500,
               uses=['continuous_dado','stair_dado']+(['square_dado'] if length==3000 else []))
        products[p['id']]=p
    return products

OPTIONS={'dado_rail_id':'rail-4800','dado_square_id':'rail-3000'}
STAIR=dict(wall_length=1500,lower_landing=250,upper_landing=250,slope_length=1200)

@pytest.mark.parametrize('length,expected',[(5743,[4800,1000]),(4800,[4800]),(4900,[4800,1000]),(12001,[4800,4800,3000]),(943,[1000])])
def test_residual_stock_is_smallest_compatible(stocks,seed_data,length,expected):
    result=calculate('DADO_STRAIGHT','Dado',{'wall_length':length},OPTIONS,stocks,3)
    summary=dado_summary(result,stocks)
    purchases=[p['stock_mm'] for p in summary['purchases'] for _ in range(p['units'])]
    assert sorted(purchases)==sorted(expected)
    assert sum(p['required_mm'] for p in summary['purchases'])==length
    assert sum(p['remainder_mm'] for p in summary['purchases'])==sum(expected)-length
    assert summary['rail_count']==len(expected)
    totals=aggregate([result],stocks,seed_data['pricing'])
    assert totals['stock_material_cost']==round(sum(expected)/500,2)
    assert totals['labour_cost']==round(length/1000*seed_data['pricing']['dado_per_m_gbp'],2)
    assert sum(m['new_purchase_units'] for m in totals['materials'])==len(expected)


def test_stock_compatibility_and_kerf(stocks):
    wrong=dict(stocks['rail-1000'],id='wrong',length_mm=944,width_mm=70,price=.01)
    stocks['wrong']=wrong
    result=calculate('DADO_STRAIGHT','Dado',{'wall_length':5743},OPTIONS,stocks,3)
    assert 'wrong' not in [g['material_id'] for g in result['groups'].values()]
    for p in stocks.values():
        if p['id']=='rail-1000':p['active']=False
    result=calculate('DADO_STRAIGHT','Dado',{'wall_length':5743},OPTIONS,stocks,3)
    assert sorted(p['stock_mm'] for p in dado_summary(result,stocks)['purchases'])==[2400,4800]
    with pytest.raises(CalculationError):calculate('DADO_STRAIGHT','Dado',{'wall_length':5743},OPTIONS,stocks,-1)


def test_straight_piece_summary_from_actual_cuts(stocks):
    inputs=dict(wall_length=3000,gap_width=100,bottom_squares=4,bottom_zone_height=1000)
    result=calculate('DADO_STRAIGHT','Dado Squares Bottom',inputs,OPTIONS,stocks,3)
    assert result['geometry']['square_width']==625 and result['geometry']['square_height']==800
    summary=dado_summary(result,stocks)
    assert (summary['rail_count'],summary['horizontal'],summary['vertical'],summary['square_count'])==(1,8,8,16)
    assert sorted((p['count'],p['length_mm']) for p in summary['square'])==[(8,625),(8,800)]
    cuts=[c for g in result['groups'].values() for stock in g['strips'] for c in stock['cuts']]
    assert len(cuts)==17 and all(c['label'] for c in cuts)
    assert all(c['length_mm']<=stocks[c['material_id']]['length_mm'] for c in cuts)


def test_plain_stair_needs_only_route(stocks):
    result=calculate('DADO_STAIR','Dado',STAIR,OPTIONS,stocks,3)
    g=stair_route_geometry(1500,250,250,1200)
    assert all(result['geometry'][k]==v for k,v in g.items())
    summary=dado_summary(result,stocks)
    assert summary['rail_count']==3 and summary['square_count']==0
    assert {p['role']:p['length_mm'] for p in summary['rail']}=={'Lower landing dado':250,'Slope dado':1200,'Upper landing dado':250}
    for group in result['groups'].values():
        for stock in group['strips']:
            assert stock['used_mm']==sum(c['length_mm'] for c in stock['cuts'])+3*(len(stock['cuts'])-1)


def test_stair_route_segments_share_one_compatible_stock_length(stocks):
    result=calculate('DADO_STAIR','Dado',STAIR,OPTIONS,stocks,3)
    groups=list(result['groups'].values())
    assert len(groups)==1
    assert groups[0]['material_id']=='rail-2400'
    assert len(groups[0]['strips'])==1
    assert [cut['length_mm'] for cut in groups[0]['strips'][0]['cuts']]==[1200,250,250]


def test_stair_bottom_uses_dado_fields_and_transition_provisions(stocks):
    inputs=dict(STAIR,gap_width=100,bottom_squares=4,bottom_zone_height=1000,
                height='ignored',horizontal_squares=0,vertical_squares=0,slat_width=900)
    result=calculate('DADO_STAIR','Dado Squares Bottom',inputs,OPTIONS,stocks,3)
    g=result['geometry'];assert g['square_width']==250 and g['square_height']==800
    assert [c['type'] for c in g['columns']]==['transition','angled','angled','transition']
    summary=dado_summary(result,stocks)
    assert (summary['rail_count'],summary['horizontal'],summary['vertical'],summary['square_count'])==(3,12,8,20)
    assert any(p['kind']=='Transition — trim to fit' for p in summary['square'])
    zero=calculate('DADO_STAIR','Dado Squares Bottom',inputs,OPTIONS,stocks,0)
    assert zero['geometry']==g
    assert dado_summary(zero,stocks)['square']==summary['square']
    with pytest.raises(CalculationError):calculate('DADO_STAIR','Dado Squares Bottom',dict(STAIR,gap_width=100),OPTIONS,stocks,3)


@pytest.mark.parametrize('style',[s for s in DADO_STYLES if s not in ('Dado','Dado Squares Bottom')])
def test_unsupported_styles_rejected(stocks,style):
    for kind in ('DADO_STRAIGHT','DADO_STAIR'):
        with pytest.raises(CalculationError,match='coming later'):calculate(kind,style,STAIR,OPTIONS,stocks,3)


def test_saved_disabled_style_is_retained(app,signed_in):
    from test_application import create_quote,add_room,add_item,post_quote
    from test_calculations import HALF
    from app.models import db,Quote,WorkItem
    qid=create_quote(signed_in,app);rid=add_room(signed_in,app,qid,'Existing quote')
    iid=add_item(signed_in,app,qid,rid,'Old saved item','PANELLING_HALF',HALF)
    with app.app_context():
        item=db.session.get(WorkItem,iid);item.type='DADO_STRAIGHT';item.subtype='Dado Double Squares Bottom';db.session.commit()
        result=deepcopy(item.result);snapshot=deepcopy(db.session.get(Quote,qid).snapshot)
    response=post_quote(signed_in,app,qid,'edit_item',room_id=rid,item_id=iid,type='DADO_STRAIGHT',subtype='Dado Double Squares Bottom',name='Changed')
    assert response.status_code==200 and b'kept unchanged' in response.data
    post_quote(signed_in,app,qid,'refresh_prices')
    with app.app_context():
        item=db.session.get(WorkItem,iid)
        assert item.name=='Old saved item' and item.subtype=='Dado Double Squares Bottom' and item.result==result
        assert db.session.get(Quote,qid).snapshot==snapshot
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert 'disabled value="Dado Double Squares Bottom" selected' in page
    assert 'Dado Double Squares Bottom — Coming later' in page
