import gzip
import json
import unittest

from earnings_monitor.sec_adapter import (
    decode_sec_payload,
    normalize_cik,
    resolve_form4_xml_url,
)


class SecAdapterTests(unittest.TestCase):
    def test_gzip_json_payload_is_decoded(self):
        payload = {"name": "Example", "cik": 320193}
        raw = gzip.compress(json.dumps(payload).encode("utf-8"))
        self.assertEqual(decode_sec_payload(raw, content_encoding="gzip", as_json=True), payload)

    def test_plain_xml_payload_is_not_decompressed(self):
        raw = b"<ownershipDocument></ownershipDocument>"
        self.assertEqual(decode_sec_payload(raw, content_encoding=None, as_json=False), raw.decode())

    def test_malformed_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            decode_sec_payload(b"not-json", content_encoding=None, as_json=True)

    def test_cik_is_zero_padded_to_ten_digits(self):
        self.assertEqual(normalize_cik("320193"), "0000320193")
        self.assertEqual(normalize_cik(320193), "0000320193")

    def test_invalid_cik_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_cik("ABC")

    def test_xsl_primary_document_resolves_to_real_ownership_xml(self):
        filing_url = "https://www.sec.gov/Archives/edgar/data/320193/000114036126025622/"
        result = resolve_form4_xml_url(
            filing_url,
            primary_document="xslF345X06/form4.xml",
            directory_listing=["xslF345X06/form4.xml", "form4.xml"],
        )
        self.assertEqual(result, filing_url + "form4.xml")

    def test_absolute_xml_link_is_preserved(self):
        result = resolve_form4_xml_url(
            "https://www.sec.gov/Archives/edgar/data/1/2/",
            primary_document="https://www.sec.gov/Archives/edgar/data/1/2/form4.xml",
            directory_listing=[],
        )
        self.assertEqual(result, "https://www.sec.gov/Archives/edgar/data/1/2/form4.xml")


if __name__ == "__main__":
    unittest.main()
