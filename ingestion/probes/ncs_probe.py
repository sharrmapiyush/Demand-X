import urllib.request
import urllib.parse
import json
import ssl

def probe_ncs():
    url = "https://www.ncs.gov.in/"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Maharashtra-Labour-Market-Platform/0.1 (Research/Pilot)"
        }
    )

    context = ssl.create_default_context()
    # disable verification if needed or keep default
    try:
        with urllib.request.urlopen(req, timeout=10, context=context) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            html_snippet = response.read(2000).decode("utf-8", errors="ignore")
            print(f"Status: {status}")
            print(f"Content-Type: {content_type}")
            print(f"Snippet length: {len(html_snippet)}")
            return {"status": status, "content_type": content_type, "accessible": True}
    except Exception as e:
        print(f"Error accessing NCS: {e}")
        return {"accessible": False, "error": str(e)}

if __name__ == "__main__":
    res = probe_ncs()
    print(json.dumps(res, indent=2))
