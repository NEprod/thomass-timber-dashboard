"""Group installed measurements for display; never combine cut requirements."""
import json


def installed_groups(layout):
    grouped={}
    for record in layout['installed_components']:
        measurements=record['measurements']
        signature=None
        if measurements:
            signature=dict(measurements)
            signature.pop('vertex_indices',None)
            signature.pop('path_vertex_indices',None)
            if 'edges' in signature:
                signature['edges']=[{k:v for k,v in edge.items() if k not in ('start_index','end_index')} for edge in signature['edges']]
                signature['angles']=[a['internal_angle_deg'] for a in signature['angles']]
        def rounded(value):
            if isinstance(value,float):return round(value,2)
            if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
            if isinstance(value,list):return [rounded(v) for v in value]
            return value
        key=json.dumps(rounded([record['component'],record['status'],signature,
            record['prepare_length_mm'],record['prepare_dimensions'],record.get('reason'),record.get('cut_status'),record.get('base_cut_length_mm')]),sort_keys=True)
        if key not in grouped:grouped[key]=dict(record,quantity=0,labels=[])
        grouped[key]['quantity']+=1
        grouped[key]['labels'].append(record['label'])
    return list(grouped.values())
