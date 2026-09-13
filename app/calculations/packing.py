"""First-fit packing recovered from legacy layout_strips.
Contract: kerf only BETWEEN cuts; labels stay attached; stock is never exceeded.
"""
import math

class CalculationError(ValueError):
    pass

def number(value, label, minimum=0, maximum=100000, allow_zero=False):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise CalculationError(f'{label} is required and must be a number.') from None
    if not math.isfinite(result) or result < minimum or result > maximum or (result == 0 and not allow_zero):
        raise CalculationError(f'{label} must be {"at least" if allow_zero else "greater than"} {minimum} and no more than {maximum}.')
    return result

def pack(cuts, stock_length, kerf, *, descending=True):
    stock_length = number(stock_length, 'Stock dimension')
    kerf = number(kerf, 'Kerf', allow_zero=True, maximum=50)
    if len(cuts) > 20000:
        raise CalculationError('Too many cuts in one calculation.')
    strips = []
    for cut in sorted(cuts, key=lambda c: -c['length_mm']) if descending else cuts:
        length = number(cut['length_mm'], 'Cut length')
        if length > stock_length + 1e-7:
            raise CalculationError(f"{cut.get('label', 'Cut')}: {length:g} mm exceeds {stock_length:g} mm stock. This piece cannot be joined automatically.")
        for strip in strips:
            used = strip['used_mm'] + kerf + length
            if used <= stock_length + 1e-7:
                strip['cuts'].append(cut)
                strip['used_mm'] = round(used, 6)
                break
        else:
            strips.append({'cuts': [cut], 'used_mm': length})
    for i, strip in enumerate(strips, 1):
        strip.update(index=i, remainder_mm=round(stock_length-strip['used_mm'],6),
                     kerf_loss_mm=round(kerf * max(0,len(strip['cuts'])-1),6))
    return strips

def split_run(length, stock_length):
    """Preserve installed run length. Blade loss belongs to stock, not the wall."""
    length = number(length, 'Run length', allow_zero=True)
    stock_length = number(stock_length, 'Stock length')
    if length == 0:
        return []
    count = math.ceil(length / stock_length)
    if count > 1000:
        raise CalculationError('Run requires too many joins for this calculation.')
    return [stock_length] * (count-1) + [round(length-stock_length*(count-1),6)]
