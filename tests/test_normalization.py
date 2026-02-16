import unittest
from decimal import Decimal

from concilia_pdfs.utils.normalization import normalize_text, parse_brl_value


class TestNormalization(unittest.TestCase):

    def test_normalize_text(self):
        self.assertEqual(normalize_text("  TESTE COM   ESPAÇOS  "), "teste com espacos")
        self.assertEqual(normalize_text("Acentuação e Çedilha"), "acentuacao e cedilha")
        self.assertEqual(normalize_text("!@#$Remove Caracteres Especiais$#@!"), "remove caracteres especiais")
        self.assertEqual(normalize_text("Pagamento de Conta - TÍTULO"), "pagamento de conta titulo")
        self.assertEqual(normalize_text(123), "")

    def test_parse_brl_value(self):
        self.assertEqual(parse_brl_value("1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_brl_value("R$ 789,10"), Decimal("789.10"))
        self.assertEqual(parse_brl_value("-45,67"), Decimal("-45.67"))
        self.assertEqual(parse_brl_value("123.45"), Decimal("123.45"))
        self.assertEqual(parse_brl_value("1,000"), Decimal("1000.00"))
        self.assertEqual(parse_brl_value("R$ -2.000,00"), Decimal("-2000.00"))
        self.assertIsNone(parse_brl_value("invalid value"))
        self.assertIsNone(parse_brl_value("1.2.3,4"))


if __name__ == '__main__':
    unittest.main()
