import json
import re
from pathlib import Path
from .models import db, Material, PricingConfig

_CABINET_PRODUCTS = {'mdf-18mm', 'mdf-mr-18mm', 'mdf-mr-9mm', 'pse-100x25-2.4m'}


def _matching_cabinet_product(row):
    """Retain an existing equivalent product, including its user-edited price."""
    candidates = db.session.scalars(db.select(Material).where(
        Material.category == row['category'], Material.length_mm == row['length_mm'],
        Material.width_mm == row['width_mm'], Material.thickness_mm == row['thickness_mm'])).all()
    def moisture_resistant(label, profile):
        return bool(re.search(r'\bmr\b|moisture[\s_-]*resistant', f'{label} {profile}', re.I))
    return any(row['category'] == 'pse' or
               moisture_resistant(product.label, product.profile) ==
               moisture_resistant(row['label'], row['profile']) for product in candidates)


def seed():
    data=json.loads((Path(__file__).parent/'data/catalogue.json').read_text())
    for row in data['materials']:
        if db.session.get(Material,row['id']) is None:
            if row['id'] not in _CABINET_PRODUCTS or not _matching_cabinet_product(row):
                db.session.add(Material(**row))
    if db.session.get(PricingConfig,1) is None:
        db.session.add(PricingConfig(id=1,values=data['pricing']))
    else:
        config = db.session.get(PricingConfig,1)
        values = dict(config.values)
        for key, value in data['pricing'].items():
            values.setdefault(key, value)
        config.values = values
    db.session.commit()
