"""Canonical item presentation shared by cases, inventory, upgrades and market."""
def present(row):
    r=dict(row)
    if r.get('display_name'):r['name']=r['display_name']
    if r.get('catalog_value') is not None:r['reference_value']=r['catalog_value']
    r['sale_available']=r.get('sell_price') is not None
    if r.get('sell_price') is not None:r['sell_price']=int(r['sell_price'])
    return r

def sale_price(c,item):
    from services.economy import EconomyError
    row=c.execute('SELECT sell_price FROM items WHERE id=?',(item,)).fetchone()
    if not row or row['sell_price'] is None:raise EconomyError('Цена мгновенного выкупа этого предмета ещё не утверждена. Предмет можно сохранить или выставить на рынок.')
    return row['sell_price']
