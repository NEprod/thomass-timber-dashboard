"""Pack existing labelled finished cuts into compatible stock within each room."""
from collections import defaultdict

from .packing import CalculationError, pack
from .pricing import money
from .sheet_optimizer import pack_sheet_parts


def _wall_spread(stocks):
    locations = defaultdict(set)
    for index, stock in enumerate(stocks):
        for cut in stock['cuts']:
            if cut.get('work_item_id') is not None:
                locations[cut['work_item_id']].add(index)
    return sum(len(indices) - 1 for indices in locations.values())


def _pack_with_wall_affinity(cuts, stock_length, kerf):
    """Prefer wall grouping only when the stock count is unchanged."""
    baseline = pack(cuts, stock_length, kerf)
    if not any(cut.get('work_item_id') is not None for cut in cuts):
        return baseline
    grouped = []
    for cut in sorted(cuts, key=lambda cut: (cut.get('work_item_id') or '', -cut['length_mm'], cut['id'])):
        same_wall = [stock for stock in grouped if any(
            previous.get('work_item_id') == cut.get('work_item_id') for previous in stock['cuts'])]
        fit = next((stock for stock in same_wall + [stock for stock in grouped if stock not in same_wall]
                    if stock['used_mm'] + kerf + cut['length_mm'] <= stock_length + 1e-7), None)
        if fit is None:
            grouped.append({'cuts': [cut], 'used_mm': cut['length_mm']})
        else:
            fit['cuts'].append(cut)
            fit['used_mm'] = round(fit['used_mm'] + kerf + cut['length_mm'], 6)
    if len(grouped) > len(baseline):
        return baseline
    for index, stock in enumerate(grouped, 1):
        stock.update(index=index, remainder_mm=round(stock_length - stock['used_mm'], 6),
                     kerf_loss_mm=round(kerf * (len(stock['cuts']) - 1), 6))
    return grouped if len(grouped) < len(baseline) or _wall_spread(grouped) < _wall_spread(baseline) else baseline


def _dado_use(cut):
    info = cut.get('angle_information') or {}
    if info.get('dado_role') == 'square' or 'square' in cut.get('role', '').lower():
        return 'square_dado'
    return 'stair_dado' if 'slope_angle' in info else 'continuous_dado'


def _dado_stocks(cuts, catalogue, kerf, source_ids):
    first = catalogue[cuts[0]['material_id']]
    products = sorted((product for product in catalogue.values()
                       if product['category'] == 'dado'
                       and (product.get('active', True) or product['id'] in source_ids)
                       and all(product[key] == first[key] for key in ('profile', 'width_mm', 'thickness_mm'))),
                      key=lambda product: (product['length_mm'], product['price'], product['id']))
    ordered = sorted(cuts, key=lambda cut: (-cut['length_mm'], cut['id']))
    plans = []
    for base in products:
        for affinity in (False, True):
            bins = []
            candidates = (sorted(cuts, key=lambda cut: (cut.get('work_item_id') or '', -cut['length_mm'], cut['id']))
                          if affinity else ordered)
            for cut in candidates:
                use = _dado_use(cut)
                suitable = [bin_ for bin_ in bins if use in bin_['product'].get('uses', []) and
                            bin_['used_mm'] + kerf + cut['length_mm'] <= bin_['product']['length_mm'] + 1e-7]
                if affinity:
                    suitable.sort(key=lambda bin_: not any(previous.get('work_item_id') == cut.get('work_item_id')
                                                            for previous in bin_['cuts']))
                if suitable:
                    bin_ = suitable[0]
                    bin_['cuts'].append(cut)
                    bin_['used_mm'] = round(bin_['used_mm'] + kerf + cut['length_mm'], 6)
                else:
                    eligible = [product for product in products
                                if use in product.get('uses', []) and product['length_mm'] >= cut['length_mm']]
                    if not eligible:
                        raise CalculationError(f"{cut['label']}: no compatible continuous dado stock fits this cut.")
                    product = base if base in eligible else eligible[0]
                    bins.append({'product': product, 'cuts': [cut], 'used_mm': cut['length_mm']})
            stock_mm = sum(bin_['product']['length_mm'] for bin_ in bins)
            long_stock_mm = sum(max(0, bin_['product']['length_mm'] -
                                    (bin_['product'].get('preferred_stock_mm') or 3000)) for bin_ in bins)
            score = (stock_mm, long_stock_mm, len(bins),
                     money(sum(bin_['product']['price'] for bin_ in bins)),
                     _wall_spread(bins), tuple(bin_['product']['id'] for bin_ in bins))
            plans.append((score, bins))
    if not plans:
        raise CalculationError('No compatible dado stock is available for this room.')
    bins = min(plans, key=lambda plan: plan[0])[1]
    stocks = []
    for bin_ in bins:
        product = bin_['product']
        assigned = [dict(cut, material_id=product['id']) for cut in bin_['cuts']]
        strip = pack(assigned, product['length_mm'], kerf)[0]
        stocks.append(dict(material_id=product['id'], category='dado',
                           stock_length_mm=product['length_mm'], stock_width_mm=product['width_mm'],
                           cuts=strip['cuts'], used_mm=strip['used_mm'],
                           kerf_loss_mm=strip['kerf_loss_mm'], remainder_mm=strip['remainder_mm']))
    return stocks


def _coving_stocks(cuts, catalogue, kerf, source_ids):
    """Pack continuous Coving members into its compatible 3000/3600 stock."""
    first = catalogue[cuts[0]['material_id']]
    products = sorted((p for p in catalogue.values() if p['category'] == 'coving'
                       and (p.get('active', True) or p['id'] in source_ids)
                       and all(p[k] == first[k] for k in ('profile', 'width_mm', 'thickness_mm'))),
                      key=lambda p: (p['length_mm'], p['price'], p['id']))
    if not products:
        raise CalculationError('No compatible Coving stock is available for this room.')
    plans = []
    orders = [sorted(cuts, key=lambda c: (-c['length_mm'], c['id'])),
              sorted(cuts, key=lambda c: (c.get('work_item_id') or '', -c['length_mm'], c['id']))]
    for base in products:
        for order in orders:
            bins = []
            for cut in order:
                suitable = [b for b in bins if b['used_mm'] + kerf + cut['length_mm'] <= b['product']['length_mm'] + 1e-7]
                suitable.sort(key=lambda b: (not any(c.get('work_item_id') == cut.get('work_item_id') for c in b['cuts']),
                                             b['product']['length_mm'] - b['used_mm']))
                if suitable:
                    bin_ = suitable[0]
                    bin_['cuts'].append(cut)
                    bin_['used_mm'] = round(bin_['used_mm'] + kerf + cut['length_mm'], 6)
                else:
                    eligible = [p for p in products if p['length_mm'] >= cut['length_mm']]
                    if not eligible:
                        raise CalculationError(f"{cut.get('label', 'Coving run')}: no continuous Coving stock fits this cut.")
                    product = base if base in eligible else eligible[0]
                    bins.append({'product': product, 'cuts': [cut], 'used_mm': cut['length_mm']})
            # A longer candidate may save a whole stock piece; shrink each resulting bin
            # back to the shortest length that still holds its kerf-aware cuts.
            for bin_ in bins:
                bin_['product'] = next(p for p in products if p['length_mm'] + 1e-7 >= bin_['used_mm'])
            score = (len(bins), sum(b['product']['length_mm'] for b in bins),
                     _wall_spread(bins), money(sum(b['product']['price'] for b in bins)),
                     tuple(b['product']['id'] for b in bins),
                     tuple(tuple(c['id'] for c in b['cuts']) for b in bins))
            plans.append((score, bins))
    bins = min(plans, key=lambda p: p[0])[1]
    stocks = []
    for bin_ in bins:
        product = bin_['product']
        packed = pack([dict(c, material_id=product['id']) for c in bin_['cuts']], product['length_mm'], kerf)[0]
        stocks.append(dict(material_id=product['id'], category='coving',
                           stock_length_mm=product['length_mm'], stock_width_mm=product['width_mm'],
                           cuts=packed['cuts'], used_mm=packed['used_mm'],
                           kerf_loss_mm=packed['kerf_loss_mm'], remainder_mm=packed['remainder_mm']))
    return stocks


def pack_rooms(rooms, catalogue, kerf, *, coving_kerf=10, sheet_trim=10, sheet_kerf=3):
    """Return chargeable stock and a workshop plan, without altering item results."""
    room_stocks = []
    room_demands = defaultdict(lambda: defaultdict(list))
    material_rows = {}
    for room in rooms:
        buckets = defaultdict(list)
        mdf_rips = defaultdict(list)
        sheet_parts = defaultdict(list)
        for item in room['items']:
            result = item['result']
            if not result.get('valid'):
                continue
            for part in result.get('sheet_parts', []):
                sheet_parts[part['material_id']].append(dict(part, room_id=room['id'],
                    room_name=room['name'], wall_name=item['name'], work_item_id=str(item['id'])))
            for group in result.get('groups', {}).values():
                product = catalogue[group['material_id']]
                family = (('dado', product['profile'], product['width_mm'], product['thickness_mm'])
                          if product['category'] in ('dado', 'coving')
                          else ('product', product['id']))
                for cut in group['cuts']:
                    labelled = dict(cut, work_item_id=cut.get('work_item_id') or str(item['id']),
                                    wall_name=item['name'], room_name=room['name'])
                    buckets[(family, group['width_mm'])].append(labelled)
        for (family, width), cuts in buckets.items():
            product = catalogue[cuts[0]['material_id']]
            group_kerf = coving_kerf if product['category'] == 'coving' else kerf
            if product['category'] == 'mdf':
                strips = _pack_with_wall_affinity(cuts, product['length_mm'], kerf)
                for index, strip in enumerate(strips, 1):
                    source_items = {cut['work_item_id'] for cut in strip['cuts']}
                    rip = dict(id=f"{room['id']}:{product['id']}:{width}:{index}",
                               length_mm=width, width_mm=width,
                               used_length_mm=strip['used_mm'],
                               label=f'{width:g} mm MDF rip',
                               finished_cuts=strip['cuts'],
                               work_item_id=next(iter(source_items)) if len(source_items)==1 else None,
                               wall_names=sorted({cut['wall_name'] for cut in strip['cuts']}))
                    mdf_rips[product['id']].append(rip)
                    room_demands[product['id']][room['id']].append(dict(
                        id=rip['id'], length_mm=strip['used_mm'], width_mm=width,
                        label=rip['label']))
            elif product['category'] == 'dado':
                source_ids = {cut['material_id'] for cut in cuts}
                for stock in _dado_stocks(cuts, catalogue, kerf, source_ids):
                    stock.update(room_id=room['id'], room_name=room['name'])
                    room_stocks.append(stock)
                    for cut in stock['cuts']:
                        room_demands[stock['material_id']][room['id']].append(
                            dict(cut, _inventory_id=cut['id']))
            elif product['category'] == 'coving':
                source_ids = {cut['material_id'] for cut in cuts}
                for stock in _coving_stocks(cuts, catalogue, group_kerf, source_ids):
                    stock.update(room_id=room['id'], room_name=room['name'])
                    room_stocks.append(stock)
                    for cut in stock['cuts']:
                        room_demands[stock['material_id']][room['id']].append(
                            dict(cut, _inventory_id=cut['id']))
            else:
                for stock in _pack_with_wall_affinity(cuts, product['length_mm'], group_kerf):
                    room_stocks.append(dict(room_id=room['id'], room_name=room['name'],
                                            material_id=product['id'], category=product['category'],
                                            stock_length_mm=product['length_mm'],
                                            stock_width_mm=product['width_mm'],
                                            cuts=stock['cuts'], used_mm=stock['used_mm'],
                                            kerf_loss_mm=stock['kerf_loss_mm'],
                                            remainder_mm=stock['remainder_mm']))
                    for cut in stock['cuts']:
                        room_demands[product['id']][room['id']].append(
                            dict(cut, _inventory_id=cut['id']))
        for material_id, rips in mdf_rips.items():
            product = catalogue[material_id]
            for board in _pack_with_wall_affinity(rips, product['width_mm'], kerf):
                room_stocks.append(dict(room_id=room['id'], room_name=room['name'],
                                        material_id=material_id, category='mdf',
                                        stock_length_mm=product['length_mm'],
                                        stock_width_mm=product['width_mm'],
                                        cuts=board['cuts'], used_mm=board['used_mm'],
                                        kerf_loss_mm=board['kerf_loss_mm'],
                                        remainder_mm=board['remainder_mm'],
                                        strip_stock_mm=sum(product['length_mm'] for _ in board['cuts']),
                                        finished_kerf_mm=sum(
                                            pack(rip['finished_cuts'], product['length_mm'], kerf)[0]['kerf_loss_mm']
                                            for rip in board['cuts'])))
        for material_id, parts in sheet_parts.items():
            product = catalogue[material_id]
            for board in pack_sheet_parts(parts, product['length_mm'], product['width_mm'],
                                          trim=sheet_trim, kerf=sheet_kerf):
                room_stocks.append(dict(room_id=room['id'], room_name=room['name'],
                    material_id=material_id, category='mdf', packing_kind='sheet',
                    stock_length_mm=product['length_mm'], stock_width_mm=product['width_mm'],
                    cuts=board['placements'], sheet_tree=board['tree'],
                    sheet_cut_lines=board['cut_lines'],
                    sheet_offcuts=board['offcuts'], trim_mm=sheet_trim,
                    kerf_loss_mm=0, remainder_mm=0,
                    used_mm=sum(p['length_mm'] * p['width_mm'] for p in board['placements'])))
                room_demands[material_id][room['id']].extend(
                    dict(part, _inventory_id=part['id']) for part in board['placements'])
    for stock in room_stocks:
        product = catalogue[stock['material_id']]
        row = material_rows.setdefault(product['id'], dict(
            material_id=product['id'], label=product['label'], category=product['category'],
            required_mm=0, allocated_existing_mm=0, new_purchase_units=0,
            strip_stock_mm=0, kerf_loss_mm=0, stocks=[], boards=[]))
        row['new_purchase_units'] += 1
        if stock.get('packing_kind') == 'sheet':
            row['required_mm'] += sum(cut['cut_length_mm'] for cut in stock['cuts'])
            row['strip_stock_mm'] += stock['stock_length_mm']
        else:
            row['required_mm'] += sum(
                sum(cut['length_mm'] for cut in rip['finished_cuts']) for rip in stock['cuts']
            ) if product['category'] == 'mdf' else sum(cut['length_mm'] for cut in stock['cuts'])
            row['strip_stock_mm'] += (stock['strip_stock_mm'] if product['category'] == 'mdf'
                                      else stock['stock_length_mm'])
            row['kerf_loss_mm'] += (stock['finished_kerf_mm'] if product['category'] == 'mdf'
                                    else stock['kerf_loss_mm'])
        row['boards' if product['category'] == 'mdf' else 'stocks'].append(stock)
    for material_id, row in material_rows.items():
        product = catalogue[material_id]
        row['required_m'] = round(row.pop('required_mm') / 1000, 6)
        row['purchased_strip_m'] = round(row.pop('strip_stock_mm') / 1000, 6)
        row['remainder_m'] = round(row['purchased_strip_m'] - row['required_m'] - row['kerf_loss_mm'] / 1000, 6)
        row['cost'] = money(row['new_purchase_units'] * product['price'])
        row['room_demands'] = [dict(room_id=room_id, cuts=demands)
                               for room_id, demands in room_demands[material_id].items()]
        if product['category'] == 'mdf':
            row['purchased_area_m2'] = round(row['new_purchase_units'] * product['length_mm'] * product['width_mm'] / 1e6, 6)
            row['rip_remainder_area_m2'] = round(sum(stock['remainder_mm'] for stock in row['boards']
                if stock.get('packing_kind') != 'sheet') * product['length_mm'] / 1e6, 6)
    return list(material_rows.values()), room_stocks
