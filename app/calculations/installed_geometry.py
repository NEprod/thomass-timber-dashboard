"""Measurements of existing installed primitives, never workshop cut formulas.

Vertex indices refer to the canonical SVG element. Profile reference paths do
not certify unmodelled inner edges or physical long-point cutting conventions.
"""
import math


def _vertices(points):
    indices = []
    for i, point in enumerate(points):
        if not indices or math.dist(points[indices[-1]], point) > 1e-7:
            indices.append(i)
    if len(indices)>1 and math.dist(points[indices[0]], points[indices[-1]])<1e-7:
        indices.pop()
    while len(indices)>3:
        removed = False
        for j, i in enumerate(indices):
            a, b, c = points[indices[j-1]], points[i], points[indices[(j+1)%len(indices)]]
            u, v = (b[0]-a[0],b[1]-a[1]), (c[0]-b[0],c[1]-b[1])
            if abs(u[0]*v[1]-u[1]*v[0]) <= 1e-7 * max(1,math.hypot(*u)*math.hypot(*v)) and u[0]*v[0]+u[1]*v[1]>=0:
                indices.pop(j); removed=True; break
        if not removed:break
    return indices


def polygon_measurements(points):
    """Measure polygon edges/angles without changing any canonical vertices."""
    indices = _vertices(points)
    area = sum(points[a][0]*points[b][1]-points[b][0]*points[a][1]
               for a,b in zip(indices,indices[1:]+indices[:1]))
    sign = 1 if area>=0 else -1
    edges, angles = [], []
    for j, i in enumerate(indices):
        previous, following = indices[j-1],indices[(j+1)%len(indices)]
        a,b,c = points[previous],points[i],points[following]
        incoming=(b[0]-a[0],b[1]-a[1]);outgoing=(c[0]-b[0],c[1]-b[1])
        turn=math.degrees(math.atan2(incoming[0]*outgoing[1]-incoming[1]*outgoing[0], incoming[0]*outgoing[0]+incoming[1]*outgoing[1]))
        angles.append(dict(vertex_index=i,internal_angle_deg=180-sign*turn))
        edges.append(dict(start_index=i,end_index=following,length_mm=math.dist(b,c),
                          angle_deg=math.degrees(math.atan2(outgoing[1],outgoing[0]))))
    xs,ys=zip(*points)
    return dict(vertex_indices=indices,edges=edges,angles=angles,
                bounding_width_mm=max(xs)-min(xs),bounding_height_mm=max(ys)-min(ys))


def _member(points, vertical=False, axis=None):
    if len(points)!=4:
        # Clipping at a short landing can add vertices. The material axis still
        # defines its exact blank extent; do not invent short-point references.
        axis = (0,1) if vertical else axis
        if axis is None:return {}
        projections=[p[0]*axis[0]+p[1]*axis[1] for p in points]
        return dict(long_point_mm=max(projections)-min(projections),
                    reference='Exact axial blank extent of the clipped installed polygon.')
    low,high=([points[0],points[1]],[points[3],points[2]]) if vertical else ([points[0],points[3]],[points[1],points[2]])
    a=[sum(p[i] for p in low)/2 for i in (0,1)]
    b=[sum(p[i] for p in high)/2 for i in (0,1)]
    length=math.dist(a,b)
    if not length:return {}
    axis=(0,1) if vertical else axis or ((b[0]-a[0])/length,(b[1]-a[1])/length)
    projection=lambda p:p[0]*axis[0]+p[1]*axis[1]
    lo,hi=[projection(p) for p in low],[projection(p) for p in high]
    def mitre(end):
        dx,dy=end[1][0]-end[0][0],end[1][1]-end[0][1]
        return math.degrees(math.asin(min(1,abs(dx*axis[0]+dy*axis[1])/math.hypot(dx,dy))))
    return dict(long_point_mm=max(hi)-min(lo),short_point_mm=min(hi)-max(lo),
                centreline_mm=length,start_mitre_deg=mitre(low),end_mitre_deg=mitre(high),
                longitudinal_edges_mm=[math.dist(low[0],high[0]),math.dist(low[1],high[1])],
                reference='Long/short points are projected along the member axis; centreline joins the end-seam midpoints.')


def _runs(groups):
    runs={}
    for group in groups.values():
        for cut in group['cuts']:
            key=cut.get('join_id') or cut['id']
            run=runs.setdefault(key,dict(label=cut['role'],prepare_length_mm=0,cut_ids=[],
                                        info=cut.get('angle_information') or {}))
            run['prepare_length_mm']+=cut['length_mm']*cut.get('quantity',1)
            run['cut_ids'].append(cut['id'])
    return list(runs.values())


def annotate_installed_geometry(plan, groups):
    """Attach audit metadata regenerated from this plan's existing primitives."""
    components=[]
    parts={label:p for p in plan.get('parts',[]) for label in p['labels']}
    opening_indices={}
    for index,element in enumerate(plan['elements']):
        kind,label,points=element['kind'],element['label'],element['points']
        if kind not in ('opening','mdf'):continue
        if kind=='opening':
            label=label.split(' · ')[0]
            opening_indices[label]=index
        prepared=parts.get(label)
        record=dict(label=label,component='Panel opening' if kind=='opening' else 'Vertical batten' if label.startswith('Vertical batten') else 'Rail',
            status='EXACT',element_index=index,source='Column boundaries intersect exact installed rail edges' if kind=='opening' or label.startswith('Vertical batten') else 'Parallel rail boundaries share exact mitre intersections',
            measurements=polygon_measurements(points),prepare_length_mm=prepared['prepare_length_mm'] if prepared else None,
            prepare_dimensions=None,
            cut_ids=list(prepared.get('cut_links',{}).get(label,prepared['cut_ids'])) if prepared else [])
        if kind=='opening':
            half=len(points)//2
            record['measurements']['opening']=dict(horizontal_spacing_mm=points[half-1][0]-points[0][0],
                left_vertical_mm=math.dist(points[0],points[-1]),right_vertical_mm=math.dist(points[half-1],points[half]),
                bottom_edges_mm=[edge['length_mm'] for edge in record['measurements']['edges'] if edge['start_index']<half and edge['end_index']<half],
                top_edges_mm=[edge['length_mm'] for edge in record['measurements']['edges'] if edge['start_index']>=half and edge['end_index']>=half])
        else:
            route=plan['boundaries']['bottom_outer']
            slope_vector=(route[2][0]-route[1][0],route[2][1]-route[1][1])
            length=math.hypot(*slope_vector)
            axis=tuple(v/length for v in slope_vector) if label.endswith(' · Slope') else (1,0)
            record['measurements']['member']=_member(points,label.startswith('Vertical batten'),axis)
        components.append(record)

    for member in plan.get('cut_members',[]):
        components.append(dict(member,component='Middle rail',status='EXACT',
            measurements=dict(polygon_measurements(member['vertices']),member=_member(member['vertices'],axis=member['axis'])),
            prepare_dimensions=None,source='Clipped canonical intermediate rail boundaries'))

    for run in _runs(groups):
        info=run['info'];edge=info.get('edge','')
        profile=next((p for p in plan.get('opening_profile_members',[]) if p['label']==run['label']),None)
        if profile:
            components.append(dict(profile,component='Dado square profile' if info.get('dado_role')=='square' else 'Bead / moulding',
                status='EXACT',cut_status='EXACT',prepare_length_mm=profile['base_cut_length_mm'],prepare_dimensions=None,
                cut_ids=run['cut_ids'],source='Exact opening outside edge; catalogue-width inward offsets meet at shared mitre intersections'))
            continue
        opening_label=f'Opening {info.get("square")}.{info.get("row")}'
        index=opening_indices.get(opening_label)
        if index is not None:
            # Conservative transition provisions do not identify physical bead
            # horizontal ends on the offset rail bends. Vertical reference paths
            # have exact endpoints independently of the old stock allowance.
            provisional=('vertical' not in edge and
                (bool(info.get('stock_allowance')) or plan['elements'][index].get('profile_provisional',False)))
            record=dict(label=run['label'],component='Bead / moulding',status='PROVISIONAL' if provisional else 'EXACT',cut_status='PROVISIONAL',
                reference_element_index=index,prepare_length_mm=run['prepare_length_mm'],prepare_dimensions=None,
                cut_ids=run['cut_ids'],source='Opening boundary reference path',measurements=None)
            if provisional:
                record['reason']='Prepare provision uses nominal aligned bend positions; fitted profile endpoints/joint reference are not defined on the offset rail bends.'
            else:
                points=plan['elements'][index]['points'];half=len(points)//2
                if edge=='left vertical':vertices=[0,len(points)-1]
                elif edge=='right vertical':vertices=[half-1,half]
                elif edge=='top':vertices=list(range(half,len(points)))
                else:vertices=list(range(half))
                record['measurements']=dict(path_vertex_indices=vertices,
                    path_length_mm=sum(math.dist(points[a],points[b]) for a,b in zip(vertices,vertices[1:])),
                    reference='Installed opening-boundary path; physical profile inner-edge/long-point convention is not modelled.')
                record['reason']='Exact opening-boundary reference only; physical profile end/inner-edge convention is not defined. Trim to fit on site.'
            components.append(record)
        elif info.get('dado_role')=='square':
            components.append(dict(label=run['label'],component='Dado square profile',status='PROVISIONAL',
                prepare_length_mm=run['prepare_length_mm'],prepare_dimensions=None,cut_ids=run['cut_ids'],measurements=None,
                source='Borrowed stair grid reference',
                reason='Reference frame is not a material-width profile polygon; fitted profile endpoints/long-point convention are not defined.'))
        elif info.get('dado_role')=='rail':
            profile=plan.get('profile_members',{}).get(run['label'])
            if profile:
                components.append(dict(label=run['label'],component='Dado',status='EXACT',
                    vertices=profile['vertices'],measurements=dict(polygon_measurements(profile['vertices']),member=profile['measurements']),
                    prepare_length_mm=run['prepare_length_mm'],prepare_dimensions=None,cut_ids=run['cut_ids'],cut_status='EXACT',
                    base_cut_length_mm=profile['base_cut_length_mm'],previous_prepare_length_mm=profile['previous_prepare_length_mm'],
                    source='Known profile width offset from the measured centreline; shared exact mitre seams'))
                continue
            dado_index=next((i for i,e in enumerate(plan['elements']) if e['kind']=='dado'),None)
            record=dict(label=run['label'],component='Dado',status='PROVISIONAL',
                prepare_length_mm=run['prepare_length_mm'],prepare_dimensions=None,cut_ids=run['cut_ids'],measurements=None,
                source='Existing measured Dado centreline')
            if dado_index is not None:
                points=plan['elements'][dado_index]['points']
                if 'Lower landing' in run['label']:vertices=[0,1]
                elif 'Slope' in run['label']:vertices=[1,2]
                else:vertices=[2,3]
                record.update(status='EXACT',element_index=dado_index,
                    measurements=dict(path_vertex_indices=vertices,path_length_mm=math.dist(points[vertices[0]],points[vertices[1]]),
                        start_mitre_deg=info.get('start_joint_setting'),end_mitre_deg=info.get('end_joint_setting'),
                        reference='Installed centreline path; profile long/short edges are not modelled.'))
            else:record['reason']='Additional Dado installation height/path is not defined.'
            components.append(record)
    plan['installed_components']=components
    plan['canonical_orientation']='High end Right; mirror coordinates only for High end Left'
