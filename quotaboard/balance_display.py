"""Shared labels for monetary balances, separate from points/token quotas."""
MONETARY_PLATFORMS=frozenset(('openai','dmxapi','zhipu','kimi','deepseek'))
CURRENCIES=frozenset(('CNY','USD','EUR','HKD','JPY','GBP'))

def balance_display(result):
    if result.ok and result.platform in MONETARY_PLATFORMS and not result.display.startswith('余额'):
        return '余额 '+result.display
    return result.display
