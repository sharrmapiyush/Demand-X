import urllib.request
import urllib.parse
import json
import ssl

def probe_ncs_search():
    base_url = "https://www.ncs.gov.in/job-seeker/pages/search.aspx"
    req = urllib.request.Request(
        base_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Maharashtra-Labour-Market-Platform/0.1 (Research/Pilot)"
        }
    )

    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=context) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            html_snippet = response.read(10000).decode("utf-8", errors="ignore")
            print(f"Status: {status}")
            print(f"Content-Type: {content_type}")
            print(f"HTML snippet length: {len(html_snippet)}")
            return {
                "status": status,
                "content_type": content_type,
                "html_snippet_length": len(html_snippet),
                "html_snippet_first_500": html_snippet[:500]
            }
    except Exception as e:
        print(f"Error accessing NCS search page: {e}")
        return {"accessible": False, "error": str(e)}

if __name__ == "__main__":
    res = probe_ncs_search()
    print(json.dumps(res, indent=2))
