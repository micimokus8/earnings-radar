#!/usr/bin/env python3
"""Inspect EarningsWhispers entry keys and bounded exchange-like values."""
from __future__ import annotations
import json
import sys
from datetime import date
from earnings_monitor.earningswhispers import EarningsWhispersClient

def main():
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    typ = sys.argv[2] if len(sys.argv) > 2 else "AFTER_CLOSE"
    client = EarningsWhispersClient(timeout=15)
    client._ensure_session()
    rt = {"BEFORE_OPEN": 1, "AFTER_CLOSE": 3}.get(typ, 3)
    url = f"https://www.earningswhispers.com/api/quickcaldata/{target:%Y%m%d}/{rt}"
    import urllib.request, json as j
    req=urllib.request.Request(url, headers={**client.__class__.__dict__.get('_HEADERS', {}), "User-Agent":"Mozilla/5.0", "Accept":"application/json", "X-Requested-With":"XMLHttpRequest", "Referer":"https://www.earningswhispers.com/calendar"})
    # use the client's cookie-enabled opener
    with client._opener.open(req, timeout=client.timeout) as resp:
        data=j.loads(resp.read().decode())
    rows=[]
    for item in data[:5] if isinstance(data,list) else []:
        if isinstance(item,dict):
            rows.append({"keys":sorted(item), "values":{k:item.get(k) for k in item if any(x in k.lower() for x in ('ticker','symbol','exchange','market','company','name'))}})
    print(json.dumps({"status":"PASS","count":len(data) if isinstance(data,list) else None,"rows":rows}, sort_keys=True))
if __name__=='__main__': main()

# Note: no credentials are used by this probe.
