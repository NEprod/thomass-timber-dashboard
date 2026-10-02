"""Prepared stock quantities read from accepted packing results; no packing here."""


def stock_mode(stock):
    return stock.get('packing_kind', 'rip' if stock['category'] == 'mdf' else 'linear')


def prepared_strip_count(stocks):
    """Full-length MDF rips only, excluding directly nested Cabinet sheet parts."""
    return sum(len(stock['cuts']) for stock in stocks
               if stock['category'] == 'mdf' and stock_mode(stock) == 'rip')


def sheet_cut_operation_count(stocks):
    """One recorded cut per guillotine split; no per-part or trim proxies.

    The optimiser's border is a planning/squaring allowance, not a chargeable
    operation. Only recorded split operations contribute to sheet-cut pricing.
    """
    return sum(len(stock['sheet_cut_lines']) for stock in stocks
               if stock_mode(stock) == 'sheet')
