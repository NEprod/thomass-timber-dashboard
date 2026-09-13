import json
from pathlib import Path
from .models import db, Material, PricingConfig

def seed():
    data=json.loads((Path(__file__).parent/'data/catalogue.json').read_text())
    for row in data['materials']:
        if db.session.get(Material,row['id']) is None: db.session.add(Material(**row))
    if db.session.get(PricingConfig,1) is None:
        db.session.add(PricingConfig(id=1,values=data['pricing']))
    db.session.commit()
