import requests
from bs4 import BeautifulSoup

class BaseScraper:
    def __init__(self):
        # The address where your local FlareSolverr instance is running
        self.flaresolverr_url = "http://localhost:8191/v1"
        self.driver = None  # We won't need a heavy local driver if we use FlareSolverr
        self.soup = None

    def get_html_via_flaresolverr(self, target_url):
        """Sends the request to FlareSolverr to bypass Cloudflare and returns raw HTML."""
        payload = {
            "cmd": "request.get",
            "url": target_url,
            "maxTimeout": 60000
        }
        try:
            response = requests.post(self.flaresolverr_url, json=payload, timeout=70)
            response_json = response.json()
            
            if response_json.get("status") == "ok":
                # Extract the solved HTML and the cookies (if you need them)
                html_content = response_json["solution"]["response"]
                self.cookies = response_json["solution"]["cookies"]
                return html_content
            else:
                print(f"FlareSolverr error: {response_json.get('message')}")
                return None
        except Exception as e:
            print(f"Failed to connect to FlareSolverr: {e}")
            return None

    def get_sf_num(self, sf):
        if sf == "semi-final":
            return str(0)
        if sf == "semi-final-1":
            return str(1)
        if sf == "semi-final-2":
            return str(2)