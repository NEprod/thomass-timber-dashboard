import pytest

from app.models import db, Quote
from app.services.quotes import material_plan
from test_application import create_quote, add_room, add_item
from test_calculations import FULL, HALF


@pytest.mark.parametrize('work_type,inputs', [
    ('PANELLING_FULL', FULL),
    ('PANELLING_HALF', HALF),
])
def test_existing_material_charges_are_visible_without_changing_totals(app, signed_in,
                                                                        work_type, inputs):
    quote_id = create_quote(signed_in, app)
    room_id = add_room(signed_in, app, quote_id, 'Workshop test')
    add_item(signed_in, app, quote_id, room_id, 'Panelling', work_type, inputs)

    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        totals_before = {key: quote.result[key] for key in (
            'material_cost', 'chargeable_material_cost', 'final_price',
            'mastic_units', 'mastic_cost', 'cut_cost', 'delivery_cost',
        )}
        mastic_rows = [row for row in material_plan(quote)
                       if row.get('is_calculated_consumable')]
        assert len(mastic_rows) == 1
        mastic = mastic_rows[0]
        assert mastic['calculated_quantity'] == totals_before['mastic_units']
        assert mastic['need_to_purchase_quantity'] == totals_before['mastic_units']
        assert mastic['chargeable_cost'] == totals_before['mastic_cost']
        assert mastic['extra_quantity'] == 0

    quote_page = signed_in.get(f'/quotes/{quote_id}').get_data(as_text=True)
    assert f'Mastic · {totals_before["mastic_units"]} tubes' in quote_page
    assert 'Cut charge' in quote_page
    assert 'Delivery' in quote_page
    assert 'Mastic' in quote_page

    dashboard = signed_in.get('/').get_data(as_text=True)
    assert 'Mastic' in dashboard
    assert 'tubes' in dashboard
    assert 'Delivery' not in dashboard

    with app.app_context():
        quote = db.session.get(Quote, quote_id)
        assert {key: quote.result[key] for key in totals_before} == totals_before
