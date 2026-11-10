from decimal import Decimal, ROUND_HALF_UP


def calculate_fee(cny, config):
    if cny is None or cny <= 0:
        return None
    tier = next(t for t in reversed(config['tiers']) if cny >= Decimal(str(t['from'])))
    amount = Decimal(str(tier['value']))
    if tier['type'] == 'percent':
        amount = cny * Decimal(str(config['rate'])) * amount / 100
    return int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
