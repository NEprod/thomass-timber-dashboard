"""Convert proven installed member polygons into minimum physical blank demand.

No stock optimisation or contingency is added. The existing room packers consume
these requirements. Unknown profile/joint shapes retain their site-fit provision.
"""
from copy import deepcopy
from .packing import CalculationError, split_run


def exact_base_cuts(plan, groups, catalogue):
    cuts={cut['id']:cut for group in groups.values() for cut in group['cuts']}
    for cut in cuts.values():cut.setdefault('requirement_status','PROVISIONAL')
    replacements={}
    links={}
    for part in plan['installed_components']:
        ids=part['cut_ids']
        member=(part.get('measurements') or {}).get('member')
        physical=part['status']=='EXACT' and member and part.get('cut_status')!='PROVISIONAL'
        if not ids:continue  # A displayed continuous intermediate rail has no separate demand.
        if not physical:
            part['cut_status']='PROVISIONAL'
            for cid in ids:
                cuts[cid]['requirement_status']='PROVISIONAL'
            continue
        base=round(member['long_point_mm'],6)
        if base<=0:raise CalculationError('Installed member has no positive physical blank extent.')
        originals=[cuts[cid] for cid in ids]
        first=originals[0]
        # One canonical component owns one original run, including its butt joins.
        if any(cid in replacements for cid in ids):
            raise CalculationError('Installed members have overlapping cut ownership.')
        previous=sum(c['length_mm'] for c in originals)
        stock_length=catalogue[first['material_id']]['length_mm']
        if base>stock_length and part['component'] not in ('Rail','Dado'):
            raise CalculationError(f"{part['label']}: exact base cut exceeds stock; automatic joining is not configured for this member.")
        pieces=split_run(base,stock_length)
        run_id=first.get('join_id') or first['id']
        converted=[]
        for index,length in enumerate(pieces,1):
            cut=deepcopy(first)
            cid=ids[index-1] if len(pieces)==len(ids) else f'{run_id}:base:{index}'
            cut.update(id=cid,length_mm=length,allowance_mm=0,
                join_id=run_id if len(pieces)>1 else None,
                label=first['role']+(f' · join {index}/{len(pieces)}' if len(pieces)>1 else ''),
                requirement_status='EXACT',base_cut_length_mm=length)
            info=dict(cut.get('angle_information') or {})
            setting=lambda name:round(member[name],2) if member.get(name) is not None else None
            info.update(measurement='Exact installed axial long-point blank; no contingency.',
                start_joint_setting=setting('start_mitre_deg') if index==1 else 0,
                end_joint_setting=setting('end_mitre_deg') if index==len(pieces) else 0)
            cut['angle_information']=info
            converted.append(cut)
        for cid in ids:replacements[cid]=[]
        replacements[ids[0]]=converted
        links.update({cid:[c['id'] for c in converted] for cid in ids})
        part.setdefault('previous_prepare_length_mm',previous)
        part.update(prepare_length_mm=base,
            base_cut_length_mm=base,cut_status='EXACT',cut_ids=[c['id'] for c in converted])

    for group in groups.values():
        group['cuts']=[new for cut in group['cuts'] for new in replacements.get(cut['id'],[cut])]
    # Keep the older stock-display adapter connected to the new demand as well.
    newcuts={cut['id']:cut for group in groups.values() for cut in group['cuts']}
    by_label={p['label']:p for p in plan['installed_components']}
    parts=[]
    for grouped in plan.get('parts',[]):
        for label in grouped['labels']:
            part=dict(grouped,label=label,quantity=1)
            ids=grouped['cut_links'][label]
            part['cut_ids']=list(dict.fromkeys(new for cid in ids for new in links.get(cid,[cid])))
            if ids:part['prepare_length_mm']=sum(newcuts[cid]['length_mm'] for cid in part['cut_ids'])
            measured=by_label.get(label)
            if measured and measured.get('base_cut_length_mm') is not None:
                member=measured['measurements']['member']
                part['installed_length_mm']=round(member['centreline_mm'],6) if member.get('centreline_mm') is not None else None
                part['prepare_length_mm']=measured['base_cut_length_mm']
                part['trim_to_fit']=False
            parts.append(part)
    from .wall_layout import _group_wall_parts
    plan['parts']=_group_wall_parts(parts)
    return groups
