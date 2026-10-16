"""Reserved manual rail-indicator references shared by circuit and mechanical builders."""
LED_RAILS = {'D10': '+12V', 'D11': '-12V', 'D12': '+5V'}
RESERVED_LED_REFS = frozenset(LED_RAILS)


def validate_reference(ref, purpose=''):
    if ref in RESERVED_LED_REFS and purpose != 'rail_indicator':
        raise ValueError(f'{ref} is reserved for a manual red rail indicator; integrate deliberately')
