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
            role = re.sub(r'\b(square|row|segment) \d+\b', r'\1', cut['role'], flags=re.I)
            angles = {k: v for k, v in (cut.get('angle_information') or {}).items()
                      if k not in _IDENTITY_FIELDS}
            status=cut.get('requirement_status')
            key = (role, cut['length_mm'], json.dumps(angles, sort_keys=True), cut.get('allowance_mm', 0),status)
            row = family['rows'].setdefault(key, dict(role=role, prepare_length_mm=cut['length_mm'], quantity=0,
                requirement='Base cut' if status=='EXACT' else 'Site-fit Prepare' if status=='PROVISIONAL' else None))
            row['quantity'] += cut.get('quantity', 1)
    return [dict(family, rows=list(family['rows'].values())) for family in families.values()]
