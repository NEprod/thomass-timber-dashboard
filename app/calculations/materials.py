"""Material-specific calculation settings shared by room packing paths."""

def kerf_for(product, pricing):
    """Keep existing kerfs intact while allowing Coving its own saw setting."""
    return pricing.get('coving_kerf', 10) if product.get('category') == 'coving' else pricing['kerf']
