import urllib.request
import json
import ssl

def probe_ncs_search():
    url = "https://www.ncs.gov.in/job-seeker/pages/search.aspx"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Maharashtra-Labour-Market-Platform/0.1 (Research/Pilot)"
        }
    )

    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=context) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            body = response.read(10000).decode("utf-8", errors="ignore")
            print(f"Status: {status}")
            print(f"Content-Type: {content_type}")
            print(f"Body length: {len(body)}")
            # Look for form fields or API references
            print("Snippet:")
            print(body[:2000])
            return {"status": status, "content_type": content_type, "accessible": True}
    except Exception as e:
        print(f"Error accessing NCS search: {e}")
        return {"accessible": False, "error": str(e)}

if __name__ == "__main__":
    res = probe_ncs_search()
    print(json.dumps(res, indent=2))
