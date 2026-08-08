from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import csv
import time
import re

from .base import BaseScraper

class JurorVote:
    """
    Represents a single directional voting relationship from one country to another.
    Contains both the unified ranks and the individual juror ranks.
    """
    def __init__(self, year=None, contest_round=None, from_country=None, to_country=None):
        self.year = year
        self.contest_round = contest_round
        self.from_country = from_country
        self.to_country = to_country
        
        # Unified Ranks
        self.televote_rank = None
        self.jury_rank = None
        
        # Individual Juror Ranks
        self.juror_a = None
        self.juror_b = None
        self.juror_c = None
        self.juror_d = None
        self.juror_e = None
        self.juror_f = None
        self.juror_g = None

    def is_valid(self):
        """Basic validation to ensure core routing data exists."""
        return bool(self.from_country and self.to_country and self.year)

    def __repr__(self):
        return f"<{self.year} {self.contest_round} | {self.from_country} -> {self.to_country}>"


class JurorsScraper(BaseScraper):
    """
    Heavy-duty scraper for Eurovision Juror Data.
    Uses Playwright to render the React SPA and BeautifulSoup for rapid, 
    boundary-aware DOM extraction to prevent data shifting.
    """

    def __init__(self):
        super().__init__()
        self.results = []
        self.debug_mode = True

    def log(self, message, level="INFO"):
        """Centralized logging for pipeline tracking."""
        prefix = {"INFO": "[+]", "WARN": "[!]", "ERROR": "[X]", "DEBUG": "[*]"}
        if level == "DEBUG" and not self.debug_mode:
            return
        print(f"  {prefix.get(level, '[ ]')} {message}")

    def build_url(self, year, contest_round):
        """Constructs the official eurovision.com scoreboard URL based on year and round."""
        cities = {
            2016: "stockholm", 2017: "kyiv", 2018: "lisbon", 2019: "tel-aviv",
            2020: None, 2021: "rotterdam", 2022: "turin", 2023: "liverpool",
            2024: "malmo", 2025: "basel", 2026: "vienna",
        }
        city = cities.get(year)
        if not city: 
            self.log(f"No host city mapped for year {year}.", "WARN")
            return None

        if contest_round == "final":
            return f"https://www.eurovision.com/eurovision-song-contest/{city}-{year}/{city}-{year}-grand-final/"
        if contest_round == "semi-final-2":
            return f"https://www.eurovision.com/eurovision-song-contest/{city}-{year}/{city}-{year}-second-semi-final/"
        if contest_round == "semi-final-1":
            if year == 2026:
                return f"https://www.eurovision.com/eurovision-song-contest/{city}-{year}/{city}-{year}-semi-final/"
            return f"https://www.eurovision.com/eurovision-song-contest/{city}-{year}/{city}-{year}-first-semi-final/"
        
        self.log(f"Unrecognized contest round: {contest_round}", "WARN")
        return None

    def safe_goto(self, page, url, retries=3):
        """
        Network resilience wrapper. Handles ERR_NETWORK_CHANGED, React timeouts, 
        and dismisses generic cookie banners to ensure clean DOM rendering.
        """
        for attempt in range(retries):
            try:
                self.log(f"Loading page (Attempt {attempt + 1}/{retries})...", "DEBUG")
                # wait_until="networkidle" ensures React has finished fetching API data
                page.goto(url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(2000) # Buffer for React hydration
                return True
            except Exception as e:
                self.log(f"Network issue encountered: {e}", "WARN")
                time.sleep(4)
        
        self.log(f"Failed to load {url} after {retries} attempts.", "ERROR")
        return False

    def sanitize_rank(self, raw_str):
        """Cleans ordinal strings ('12th', '1st', '-', '') into pure integers/strings."""
        if not raw_str:
            return None
        cleaned = raw_str.strip().lower()
        cleaned = re.sub(r'(st|nd|rd|th)$', '', cleaned)
        return cleaned if cleaned else None

    def extract_country_name(self, entry_element):
        """
        Multi-layered extraction logic to guarantee we find the receiving country,
        even if the layout changes slightly.
        """
        # Strategy 1: The standard aria-label
        aria_label = entry_element.get("aria-label", "")
        if "Detailed voting results for" in aria_label:
            return aria_label.replace("Detailed voting results for", "").strip()

        # Strategy 2: Look for the text inside the country-name span
        name_span = entry_element.select_one(".country-name, h3, .participant-name")
        if name_span and name_span.text:
            return name_span.text.strip()

        # Strategy 3: Look at the flag image alt text
        img_tag = entry_element.select_one("img")
        if img_tag and img_tag.get("alt"):
            return img_tag.get("alt").replace("Flag of", "").strip()

        return None

    def scrape_year(self, contest, contest_round):
        """Main orchestrator: Loads page, extracts UI list, parses DOM, audits data."""
        url = self.build_url(contest.year, contest_round)
        if not url:
            return []

        self.log(f"Initiating extraction pipeline for {contest.year} {contest_round.upper()}", "INFO")
        self.log(f"Target URL: {url}", "DEBUG")
        
        all_votes = []
        html_content = ""
        voting_countries = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            if not self.safe_goto(page, url):
                browser.close()
                return []

            # Extract the sidebar list of voting countries to establish our boundaries
            try:
                page.wait_for_selector("#country-list button.country-item", state="attached", timeout=15000)
                sidebar_buttons = page.locator("#country-list button.country-item")
                
                for i in range(sidebar_buttons.count()):
                    btn = sidebar_buttons.nth(i)
                    c_name = btn.get_attribute("data-name")
                    if c_name:
                        c_name = c_name.strip()
                        is_rotw = btn.get_attribute("data-rotw")
                        
                        # Skip Rest of the World as they don't have Jury votes
                        if is_rotw == "true" or c_name.lower() == "rest of the world":
                            continue
                        voting_countries.append(c_name)
                        
                self.log(f"Successfully identified {len(voting_countries)} voting countries in sidebar.", "INFO")
            
            except PlaywrightTimeoutError:
                self.log(f"No voting sidebar found for {contest.year} {contest_round}. Possibly cancelled or missing data.", "ERROR")
                browser.close()
                return []

            # Dump the fully-hydrated React DOM
            html_content = page.content()
            browser.close() 

        # Pass to the parsing engine
        if html_content and voting_countries:
            all_votes = self.parse_dom(html_content, contest, contest_round, voting_countries)

        # Final Cleanup & Validation
        unique_votes = self.deduplicate_votes(all_votes)
        self.log(f"Pipeline complete: {len(unique_votes)} unique vote relationships mapped.", "INFO")
        print("-" * 50)
        return unique_votes

    def parse_dom(self, html_content, contest, contest_round, voting_countries):
        """
        The core engine. Sweeps the DOM and intelligently assigns the 'From' country
        using an Alphabetical Reset detection, completely preventing data spillage.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        all_entries = soup.select("div.detailed-voting-results-entry")
        
        self.log(f"Captured {len(all_entries)} raw scoreboard rows from the DOM.", "INFO")

        if not all_entries:
            self.log("No scoreboard entries found in HTML.", "WARN")
            return []

        all_votes = []
        voter_idx = 0
        prev_target = ""
        
        # Audit tracker to prove data integrity
        audit_counts = {country: 0 for country in voting_countries}
        
        for entry in all_entries:
            if voter_idx >= len(voting_countries):
                break 

            current_voter = voting_countries[voter_idx]
            to_country = self.extract_country_name(entry)
            
            if not to_country:
                continue
                
            # --- ALPHABETICAL BOUNDARY LOGIC ---
            # Eurovision detailed rows are strictly sorted alphabetically. 
            # If the current target country alphabetically precedes the previous target,
            # the A-Z list has wrapped around, meaning we entered a new voting block!
            if prev_target and to_country.lower() < prev_target.lower():
                voter_idx += 1
                if voter_idx >= len(voting_countries):
                    break
                current_voter = voting_countries[voter_idx]
                
            prev_target = to_country
            
            # Extract detailed ranking values
            values = {}
            for wrapper in entry.select("div.data-row-entry-result-wrapper"):
                label_el = wrapper.select_one(".data-row-entry-result-label")
                spans = wrapper.find_all("span")
                
                if label_el and spans:
                    raw_val = spans[-1].text
                    key = label_el.text.strip().lower()
                    values[key] = self.sanitize_rank(raw_val)

            # Map to JurorVote Object
            vote = JurorVote(contest.year, contest_round, current_voter, to_country)
            
            vote.televote_rank = values.get("audience rank", values.get("televote rank", values.get("televote")))
            vote.jury_rank = values.get("jury rank", values.get("jury voting", values.get("jury score", values.get("jury"))))
            
            vote.juror_a = values.get("juror a", values.get("a"))
            vote.juror_b = values.get("juror b", values.get("b"))
            vote.juror_c = values.get("juror c", values.get("c"))
            vote.juror_d = values.get("juror d", values.get("d"))
            vote.juror_e = values.get("juror e", values.get("e"))
            vote.juror_f = values.get("juror f", values.get("f"))
            vote.juror_g = values.get("juror g", values.get("g"))
            
            if vote.is_valid():
                all_votes.append(vote)
                audit_counts[current_voter] += 1

        self._print_audit_report(audit_counts)
        return all_votes

    def _print_audit_report(self, audit_counts):
        """Displays a sanity-check report to guarantee no data shifted."""
        self.log("--- DATA INTEGRITY AUDIT ---", "DEBUG")
        for country, count in audit_counts.items():
            if count == 0:
                self.log(f"{country: <20} : {count} votes (WARNING: Missing Data)", "WARN")
            elif count > 26:
                self.log(f"{country: <20} : {count} votes (WARNING: Too High)", "WARN")
            else:
                self.log(f"{country: <20} : {count} votes", "DEBUG")

    def deduplicate_votes(self, votes):
        """Removes any accidental duplicate objects based on composite key."""
        seen = set()
        deduped = []
        for v in votes:
            key = (v.year, v.contest_round, v.from_country, v.to_country)
            if key not in seen:
                seen.add(key)
                deduped.append(v)
        return deduped

    def save_csv(self, rows, filename):
        """Writes data to a structured CSV format, enforcing UTF-8 for special characters."""
        if not rows:
            self.log("No data to save.", "WARN")
            return
            
        self.log(f"Writing {len(rows)} records to {filename}...", "INFO")
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "year", "round", "from_country", "to_country",
                "televote_rank", "jury_rank", "juror_A", "juror_B",
                "juror_C", "juror_D", "juror_E", "juror_F", "juror_G"
            ])
            for r in rows:
                writer.writerow([
                    r.year, r.contest_round, r.from_country, r.to_country,
                    r.televote_rank, r.jury_rank, 
                    r.juror_a, r.juror_b, r.juror_c, r.juror_d, 
                    r.juror_e, r.juror_f, r.juror_g
                ])
        self.log(f"Save successful.", "INFO")