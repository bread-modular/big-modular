"""Reserved manual rail-indicator references shared by circuit and mechanical builders."""
LED_RAILS = {'D10': '+5V POWER'}
RESERVED_LED_REFS = frozenset(('D10','D11','D12'))  # former LED refs stay reserved


def validate_reference(ref, purpose=''):
    if ref in RESERVED_LED_REFS and purpose != 'rail_indicator':
        raise ValueError(f'{ref} is reserved for a manual red rail indicator; integrate deliberately')
