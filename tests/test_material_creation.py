from app.models import db, Material
from test_application import create_quote, add_room, add_item
from test_calculations import FULL


def add_material(client, **data):
    response=client.post('/materials',data=dict(action='add_material',active='on',**data))
    assert response.status_code==302


def test_add_physical_catalogue_materials_and_active_snapshot(app, signed_in):
    add_material(signed_in,category='mdf',label='Smoke MDF 12 mm',profile='MDF',
                 length_mm=2440,width_mm=1220,thickness_mm=12,price=42.5)
    add_material(signed_in,category='bead',label='Smoke Bead 12 mm',profile='Square bead',
                 length_mm=3000,width_mm=18,thickness_mm=12,price=8.5)
    add_material(signed_in,category='dado',label='Smoke Dado 45 mm',profile='45mm',
                 length_mm=3000,width_mm=45,thickness_mm=20,price=17.5,
                 uses=['continuous_dado','stair_dado'])
    with app.app_context():
        mdf=db.session.scalar(db.select(Material).where(Material.label=='Smoke MDF 12 mm'))
        bead=db.session.scalar(db.select(Material).where(Material.label=='Smoke Bead 12 mm'))
        dado=db.session.scalar(db.select(Material).where(Material.label=='Smoke Dado 45 mm'))
        assert (mdf.category,mdf.length_mm,mdf.width_mm,mdf.thickness_mm,mdf.price,mdf.active)==('mdf',2440,1220,12,42.5,True)
        assert (bead.category,bead.profile,bead.active)==('bead','Square bead',True)
        assert (dado.category,dado.profile,dado.uses,dado.active)==('dado','45mm',['continuous_dado','stair_dado'],True)
        mdf_id=mdf.id
    qid=create_quote(signed_in,app)
    room=add_room(signed_in,app,qid,'Selector check')
    add_item(signed_in,app,qid,room,'Wall','PANELLING_FULL',FULL)
    page=signed_in.get(f'/quotes/{qid}').get_data(as_text=True)
    assert f'value="{mdf_id}"' in page


def test_add_material_rejects_malformed_dimensions(app, signed_in):
    response=signed_in.post('/materials',data=dict(action='add_material',category='mdf',
                               label='Bad board',profile='MDF',length_mm=0,width_mm=1220,
                               thickness_mm=9,price=10,active='on'))
    assert response.status_code==200
    with app.app_context():
        assert db.session.scalar(db.select(Material).where(Material.label=='Bad board')) is None
