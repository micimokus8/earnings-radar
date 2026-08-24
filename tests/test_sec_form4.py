import unittest
from datetime import date

from earnings_monitor.sec_form4 import parse_form4_xml, summarize_transactions


FORM4_M_F = """<?xml version="1.0"?>
<ownershipDocument>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>100</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>F</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>50</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""

FORM4_SELL = """<?xml version="1.0"?>
<ownershipDocument>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>125</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


class Form4Tests(unittest.TestCase):
    def test_m_and_f_are_not_sell_flag(self):
        transactions = parse_form4_xml(FORM4_M_F)
        summary = summarize_transactions(transactions)
        self.assertEqual(summary["status"], "NO_DIRECT_SELL")
        self.assertFalse(summary["sell_flag"])
        self.assertEqual(summary["codes"], ["M", "F"])

    def test_only_real_s_transaction_is_sell_flag(self):
        transactions = parse_form4_xml(FORM4_SELL)
        summary = summarize_transactions(transactions)
        self.assertEqual(summary["status"], "SELL_FLAG")
        self.assertTrue(summary["sell_flag"])
        self.assertEqual(summary["sell_shares"], 125.0)

    def test_malformed_xml_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_form4_xml("<ownershipDocument>")


if __name__ == "__main__":
    unittest.main()
