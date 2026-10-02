"""Prepared stock quantities read from accepted packing results; no packing here."""


def stock_mode(stock):
    return stock.get('packing_kind', 'rip' if stock['category'] == 'mdf' else 'linear')


def prepared_strip_count(stocks):
    """Full-length MDF rips only, excluding directly nested Cabinet sheet parts."""
    return sum(len(stock['cuts']) for stock in stocks
               if stock['category'] == 'mdf' and stock_mode(stock) == 'rip')
