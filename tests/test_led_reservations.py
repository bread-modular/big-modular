"""Mechanical-only reservation guards; no circuit generation or supplier claims."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from interface_contract import LED_RAILS, validate_reference
from stack_geometry import geometry

class LedReservationTests(unittest.TestCase):
    def test_reserved_refs_cannot_be_general_diodes(self):
        self.assertEqual(LED_RAILS,{'D10':'+12V','D11':'-12V','D12':'+5V'})
        for ref in LED_RAILS:
            with self.assertRaises(ValueError): validate_reference(ref)
            validate_reference(ref,'rail_indicator')
        validate_reference('D13')

    def test_three_nominal_lamps_clear_usb_and_bracket_envelopes(self):
        g=geometry()
        for led in g['LEDs']:
            x,y,d=led['panel_XY_diameter_mm']
            self.assertGreater(x-d/2,0)
            self.assertLess(x+d/2,g['panel_mm'][0])
            self.assertGreater(y-3.8,27.5)
            self.assertLess(y+3.8,59)
            self.assertGreater(3.6,g['LED']['max_body_diameter_mm'])
        self.assertNotIn('resistor',g)
        self.assertEqual(g['LED']['pin_roles'],{'1':'K (cathode)','2':'A (anode)'})
