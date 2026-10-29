import gzip, re, urllib.request, ssl

url = "https://yoshiizumi-dc.com/feed/"
try:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=10, context=ssl._create_unverified_context()) as r:
        print("status:", r.status)
        print("url:", r.geturl())
        print("headers:", dict(r.headers))
        data = r.read()
        print("raw len:", len(data))
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
            print("decompressed len:", len(data))
        text = data.decode("utf-8", errors="ignore")
        m = re.search(r"<generator[^>]*>[^<]*</generator>", text, re.IGNORECASE)
        print("generator tag:", m.group(0) if m else "KHÔNG THẤY")
except Exception as e:
    print("ERR:", type(e).__name__, e)