import unittest

from earnings_monitor.sec_form4_collector import collect_form4_activity


SUBMISSIONS = {
    "filings": {"recent": {
        "form": ["8-K", "4", "4", "10-K"],
        "filingDate": ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-12"],
        "accessionNumber": ["a", "0000000001-26-000001", "0000000001-26-000002", "b"],
        "primaryDocument": ["a.htm", "xslF345X06/form4.xml", "form4.xml", "b.htm"],
    }}
}

XML_NO_SELL = """<ownershipDocument><nonDerivativeTable>
<nonDerivativeTransaction><transactionCoding><transactionCode>M</transactionCode></transactionCoding></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""
XML_SELL = """<ownershipDocument><nonDerivativeTable>
<nonDerivativeTransaction><transactionCoding><transactionCode>S</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>10</value></transactionShares></transactionAmounts>
</nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""


class FakeSecClient:
    def __init__(self, submissions, xml_by_url=None, error=False):
        self.submissions = submissions
        self.xml_by_url = xml_by_url or {}
        self.error = error
        self.urls = []

    def get_json(self, url):
        if self.error:
            raise RuntimeError("request failed")
        return self.submissions

    def get_text(self, url):
        self.urls.append(url)
        if self.error:
            raise RuntimeError("request failed")
        return self.xml_by_url[url]


class SecForm4CollectorTests(unittest.TestCase):
    def test_filters_form4_by_date_and_returns_no_direct_sell(self):
        base = "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/"
        client = FakeSecClient(SUBMISSIONS, {
            base + "form4.xml": XML_NO_SELL,
            "https://www.sec.gov/Archives/edgar/data/1/000000000126000002/form4.xml": XML_NO_SELL,
        })
        result = collect_form4_activity(client, cik="1", start_date="2026-08-11", end_date="2026-08-12")
        self.assertEqual(result["status"], "NO_DIRECT_SELL")
        self.assertEqual(result["filings_checked"], 2)
        self.assertFalse(result["sell_flag"])

    def test_no_matching_filings_is_explicit_status(self):
        client = FakeSecClient(SUBMISSIONS, {})
        result = collect_form4_activity(client, cik=1, start_date="2026-08-13", end_date="2026-08-14")
        self.assertEqual(result["status"], "NO_RECENT_FILING_FOUND")
        self.assertEqual(result["filings_checked"], 0)

    def test_partial_when_one_filing_fails(self):
        class PartlyBrokenClient(FakeSecClient):
            def get_text(self, url):
                if url.endswith("000000000126000002/form4.xml"):
                    raise RuntimeError("xml failed")
                return super().get_text(url)

        client = PartlyBrokenClient(SUBMISSIONS, {
            "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/form4.xml": XML_NO_SELL,
            "https://www.sec.gov/Archives/edgar/data/1/000000000126000002/form4.xml": XML_NO_SELL,
        })
        result = collect_form4_activity(client, cik=1, start_date="2026-08-11", end_date="2026-08-12")
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["filings_checked"], 2)
        self.assertEqual(result["filings_failed"], 1)

    def test_sell_is_detected(self):
        client = FakeSecClient(SUBMISSIONS, {
            "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/form4.xml": XML_SELL,
            "https://www.sec.gov/Archives/edgar/data/1/000000000126000002/form4.xml": XML_NO_SELL,
        })
        result = collect_form4_activity(client, cik=1, start_date="2026-08-11", end_date="2026-08-12")
        self.assertEqual(result["status"], "SELL_FLAG")
        self.assertEqual(result["sell_shares"], 10.0)

    def test_request_failure_is_unknown(self):
        result = collect_form4_activity(FakeSecClient(None, error=True), cik=1, start_date="2026-08-11", end_date="2026-08-12")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["sell_flag"])


if __name__ == "__main__":
    unittest.main()
