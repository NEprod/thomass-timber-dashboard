"""Pure full/half/stair calculators adapted from the audited modular Tk source.
See docs/CALCULATIONS.md for provenance and isolated safety corrections.
"""
from dataclasses import dataclass, asdict
from .packing import CalculationError, number, pack, split_run
from .geometry import stair_geometry, WORKSHOP_ALLOWANCE_MM

TYPES = {'PANELLING_FULL':'Full square panelling','PANELLING_HALF':'Half square panelling',
         'PANELLING_STAIR_HALF':'Stair half-wall panelling'}
SUBTYPES = {'plain':'Plain','bead':'With bead','ledge':'With ledge','ledge_bead':'With ledge & bead'}
DADO_STYLES = ['Dado','Dado Squares Top & Bottom','Dado Double Squares Top & Bottom','Dado Squares Bottom','Dado Double Squares Bottom']
VERSION = '1.0-measured-legacy'

@dataclass(frozen=True)
class Cut:
    id: str
    work_item_id: str
    material_id: str
    role: str
    length_mm: float
    width_mm: float
    label: str
    quantity: int = 1
    allowance_mm: float = 0
    angle_information: dict | None = None
    join_id: str | None = None

def calculate(kind, subtype, inputs, options, catalogue, kerf, work_item_id='preview'):
    if kind not in TYPES:
        raise CalculationError('This work-item calculator is not supported in Milestone 1.')
    if subtype not in SUBTYPES or (kind=='PANELLING_FULL' and 'ledge' in subtype):
        raise CalculationError('Select a supported finish for this work type.')
    w = number(inputs.get('wall_length'), 'Wall length')
    h = number(inputs.get('height'), 'Wall / panel height')
    s = number(inputs.get('slat_width'), 'Slat width', maximum=1000)
    counts=[]
    for key,label in [('horizontal_squares','Horizontal squares'),('vertical_squares','Vertical squares')]:
        x=number(inputs.get(key),label,maximum=100)
        if not x.is_integer(): raise CalculationError(f'{label} must be a whole number.')
        counts.append(int(x))
    n,r=counts
    if n*r > 1000: raise CalculationError('Limit each work item to 1000 squares.')
    mdf = catalogue.get(str(options.get('mdf_id')))
    if not mdf or mdf['category']!='mdf': raise CalculationError('Select an MDF sheet.')
    length = number(mdf['length_mm'],'MDF stock length')
    sheet_width = number(mdf['width_mm'],'MDF sheet width')
    if s>sheet_width: raise CalculationError('Slat width exceeds the MDF sheet width.')
    number(kerf,'Kerf',allow_zero=True,maximum=50)
    sw,sh=round((w-(n+1)*s)/n,2),round((h-(r+1)*s)/r,2)
    number(sw,'Square width');number(sh,'Square height')
    geometry={'square_width':sw,'square_height':sh}
    groups={}; warnings=[]; serial=0
    def add(group, role, value, qty=1, *, material=mdf, width=s, split=False, allowance=0, angles=None):
        nonlocal serial
        pieces=split_run(value,material['length_mm']) if split else [value]
        for q in range(qty):
            join=f'{work_item_id}:{role}:{serial}' if len(pieces)>1 else None
            for i,piece in enumerate(pieces):
                serial+=1
                c=Cut(str(work_item_id)+':'+str(serial),str(work_item_id),str(material['id']),role,piece,width,
                      role+(f' · join {i+1}/{len(pieces)}' if join else ''),
                      allowance_mm=allowance if i==0 else 0,angle_information=angles,join_id=join)
                entry=groups.setdefault(group,dict(material_id=str(material['id']),width_mm=width,cuts=[]))
                entry['cuts'].append(asdict(c))
    if kind=='PANELLING_FULL':
        add('vertical','Vertical',h,n+1)
        add('horizontal','Horizontal',sw,n*(r+1))
    elif kind=='PANELLING_HALF':
        add('top_and_bottom_horizontal','Top rail',w,split=True)
        add('top_and_bottom_horizontal','Bottom rail',w,split=True)
        add('vertical','Vertical',h-2*s,n+1)
        if r>1: add('middle_horizontal','Middle horizontal',sw,n*(r-1))
    else:
        lower=number(inputs.get('lower_landing'),'Lower landing',allow_zero=True)
        upper=number(inputs.get('upper_landing'),'Upper landing',allow_zero=True)
        slope=number(inputs.get('slope_length'),'Measured slope length')
        geometry=stair_geometry(w,h,lower,upper,slope,n,r,s)
        angles={k:geometry[k] for k in ['slope_mitre','top_angle_setting','bottom_angle_setting','acute_included_angle','obtuse_included_angle','angle_convention']}
        allowance=WORKSHOP_ALLOWANCE_MM
        for role,value,adjust in [('Top (Upper Landing)',upper+allowance,allowance),('Top (Lower Landing)',max(0,lower-allowance),-min(lower,allowance)),('Bottom (Upper Landing)',upper,0),('Bottom (Lower Landing)',lower,0)]:
            add('top_and_bottom_horizontal',role,value,split=True,allowance=adjust,angles=angles)
        add('top_and_bottom_horizontal','Slope',slope,2,split=True,angles=angles)
        add('vertical','Flat',geometry['vertical_height'])
        for i,col in enumerate(geometry['columns']):
            typ=col['type']
            angled=typ=='angled' or (typ=='transition' and (i==0 or geometry['columns'][i-1]['type']=='flat'))
            add('vertical',('Angled' if angled else 'Flat')+(' (Trans)' if typ=='transition' else ''),geometry['angled_vertical_height'] if angled else geometry['vertical_height'],angles=angles)
            if r>1: add('middle_horizontal','Middle ('+typ+')',sw if typ=='flat' else geometry['angled_square_width'],r-1,angles=angles)
        warnings.append('Historical 30 mm top-landing allowance retained. Displayed angles need physical saw-orientation verification.')
    if 'ledge' in subtype:
        ledge_width=number(options.get('ledge_width'), 'Ledge rip width', maximum=sheet_width)
        run=w if kind!='PANELLING_STAIR_HALF' else lower+upper+slope
        add('ledge','Ledge',run,width=ledge_width,split=True)
        warnings.append('Ledge rip width is explicit; the historical 2× / 3× thickness choice is retained in options, not assumed as a physical thickness.')
    if 'bead' in subtype:
        bead=catalogue.get(str(options.get('bead_id')))
        if not bead or bead['category']!='bead': raise CalculationError('Select a bead profile.')
        if bead['thickness_mm']!=mdf['thickness_mm']: raise CalculationError('Bead profile thickness must match the selected MDF.')
        def perimeter(group,width,height,count):
            add(group,'Bead horizontal',width,count*2,material=bead,width=bead['width_mm'])
            add(group,'Bead vertical',height,count*2,material=bead,width=bead['width_mm'])
        if kind=='PANELLING_STAIR_HALF':
            if geometry['counts']['transition'] or r>1 or 'ledge' in subtype:
                raise CalculationError('Stair bead with transitions, multiple rows or ledge is unsupported pending workshop verification. Choose plain or ledge-only stair panelling.')
            perimeter('flat_square_beads',sw,sh,geometry['counts']['flat'])
            perimeter('angled_square_beads',geometry['angled_square_width'],geometry['angled_square_height'],geometry['counts']['angled'])
        else:
            perimeter('square_beads',sw,sh,n*r)
            if 'ledge' in subtype: add('ledge_beads','Under-ledge bead',w,material=bead,width=bead['width_mm'],split=True)
    for group in groups.values():
        group['strips']=pack(group['cuts'],catalogue[group['material_id']]['length_mm'],kerf)
    return {'valid':True,'version':VERSION,'geometry':geometry,'groups':groups,'warnings':warnings,
            'horizontal_strips':sum(len(g['strips']) for key,g in groups.items() if key in ('horizontal','top_and_bottom_horizontal','middle_horizontal')),
            'vertical_strips':len(groups.get('vertical',{}).get('strips',[]))}
