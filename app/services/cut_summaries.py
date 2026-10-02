"""Compact read-only summaries of authoritative workshop cut records."""
import json
import re


_IDENTITY_FIELDS = {'square', 'row', 'segment', 'segments', 'x_start', 'x_end'}


def cut_summary(groups):
    families = {}
    for name, group in groups.items():
        for cut in group['cuts']:
            material = cut['material_id']
            width = cut['width_mm']
            family = families.setdefault((name, material, width), dict(
                label=name.replace('_', ' ').capitalize(), material_id=material,
                width_mm=width, rows={}))
            # Remove location numbering, retaining component/edge, profile and
            # all cutting settings. Equal lengths alone are not interchangeable.
            role = re.sub(r'\b(square|row|segment) \d+\b', r'\1', cut.get('role', cut.get('label', 'Cut')), flags=re.I)
            angles = {k: v for k, v in (cut.get('angle_information') or {}).items()
                      if k not in _IDENTITY_FIELDS}
            # Pair equivalent horizontal profile edges only when their physical
            # dimensions and end settings also match. Transition segment numbers
            # remain part of the cutting key.
            edge = angles.get('edge')
            if edge in ('top', 'bottom'):
                angles['edge'] = 'top/bottom'
                role = re.sub(r'(· )(top|bottom)\b', r'\1top/bottom', role, flags=re.I)
            role = re.sub(r'\bsquare\s+row\b', '', role, flags=re.I).strip()
            role = re.sub(r'\s+', ' ', role)
            if cut.get('requirement_status') == 'EXACT' and all(
                    key in angles for key in ('start_joint_setting', 'end_joint_setting')):
                # Saw context/provenance does not change explicit fitted-end cuts.
                for key in ('measurement', 'slope_mitre', 'top_angle_setting',
                            'bottom_angle_setting', 'acute_included_angle',
                            'obtuse_included_angle', 'angle_convention'):
                    angles.pop(key, None)
            role = role.replace('(Trans)', '· Transition')
            status=cut.get('requirement_status')
            key = (role, cut['length_mm'], json.dumps(angles, sort_keys=True), cut.get('allowance_mm', 0),status)
            row = family['rows'].setdefault(key, dict(role=role, prepare_length_mm=cut['length_mm'], quantity=0,
                requirement='Base cut' if status=='EXACT' else 'Site-fit Prepare' if status=='PROVISIONAL' else None))
            row['quantity'] += cut.get('quantity', 1)
    return [dict(family, rows=list(family['rows'].values())) for family in families.values()]
