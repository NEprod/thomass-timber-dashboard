"""Physical mitred profiles inside calculator-owned opening boundaries.

The existing straight-frame convention places the outside profile edge on the
opening boundary (zero extra inset). Catalogue width extends into the opening.
Every inner corner is an intersection of adjacent parallel offset lines.
"""
import math

from .installed_geometry import _vertices, _member, polygon_measurements
from .packing import CalculationError, number


def opening_profile_members(plan, width, previous_edges, *, prefix='Bead'):
    width = number(width, 'Opening profile width', maximum=1000)
    previous = {(e['information']['square'], e['information']['row'],
                 e['information']['edge'], e['information'].get('segment', 1)): e['length_mm']
                for e in previous_edges}
    members = []
    for opening in (e for e in plan['elements'] if e['kind']=='opening'):
        points = opening['points']
        outer = [points[i] for i in _vertices(points)]
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(outer,outer[1:]+outer[:1]))
        if area <= 0:
            raise CalculationError('Opening profile requires a positive installed opening boundary.')
        lines, axes = [], []
        for a,b in zip(outer,outer[1:]+outer[:1]):
            length = math.dist(a,b)
            axis = ((b[0]-a[0])/length,(b[1]-a[1])/length)
            axes.append(axis)
            lines.append(([a[0]-axis[1]*width,a[1]+axis[0]*width],axis))
        inner = []
        for index,(b,v) in enumerate(lines):
            a,u = lines[index-1]
            cross = u[0]*v[1]-u[1]*v[0]
            if abs(cross)<1e-10:
                raise CalculationError('Opening profile corner has no unique mitre intersection.')
            t = ((b[0]-a[0])*v[1]-(b[1]-a[1])*v[0])/cross
            inner.append([a[0]+t*u[0],a[1]+t*u[1]])
        # Preserve left-to-right segment identity independently of polygon winding.
        half = len(points)//2
        bottom = {(tuple(a),tuple(b)) for a,b in zip(points[:half],points[1:half])}
        edges = []
        for index,(a,b) in enumerate(zip(outer,outer[1:]+outer[:1])):
            if math.isclose(a[0],b[0],abs_tol=1e-7):
                edge = 'left vertical' if a[0]==min(p[0] for p in outer) else 'right vertical'
            else:
                # Midpoint lies on one of the exact bottom boundary segments.
                x,y = (a[0]+b[0])/2,(a[1]+b[1])/2
                on_bottom = any(min(c[0],d[0])-1e-7<=x<=max(c[0],d[0])+1e-7 and
                    abs((x-c[0])*(d[1]-c[1])-(y-c[1])*(d[0]-c[0]))<1e-5
                    for c,d in bottom)
                edge = 'bottom' if on_bottom else 'top'
            edges.append((edge,index,min(a[0],b[0])))
        square,row = map(int,opening['label'].split(' · ')[0].replace('Opening ','').split('.'))
        family = opening['label'].split(' · ')[-1].lower()
        for edge in ('top','bottom','left vertical','right vertical'):
            matching = sorted((e for e in edges if e[0]==edge),key=lambda e:e[2])
            for segment,(_,index,_) in enumerate(matching,1):
                following = (index+1)%len(outer)
                a,b = outer[index],outer[following]
                c,d = inner[following],inner[index]
                axis = axes[index]
                if (c[0]-d[0])*axis[0]+(c[1]-d[1])*axis[1] <= 0:
                    raise CalculationError(f'Opening {square}.{row}: {width:g}mm profile cannot fit the {edge} transition segment; its mitred inner edge collapses. Select a narrower profile or revise the opening layout.')
                vertices = [a,b,c,d]
                measured = _member(vertices,axis=axis)
                role = f'{prefix} {family} square {square} row {row} · {edge}'
                if len(matching)>1:role += f' segment {segment}'
                members.append(dict(label=role,vertices=vertices,
                    measurements=dict(polygon_measurements(vertices),member=measured),
                    base_cut_length_mm=round(measured['long_point_mm'],6),
                    previous_prepare_length_mm=previous.get((square,row,edge,segment)),
                    information=dict(square=square,row=row,edge=edge,profile_segment=segment,
                        start_joint_setting=round(measured['start_mitre_deg'],2),
                        end_joint_setting=round(measured['end_mitre_deg'],2),
                        measurement='Exact physical profile long-point blank; zero extra inset, no contingency.')))
    return members
