from bs4 import BeautifulSoup
from copy import deepcopy

from .base import BaseScraper


class BettingOffice:
    def __init__(self, bm_id: int, sc_id: int, name: str):
        self.bm_id = bm_id
        self.sc_id = sc_id
        self.name = name
        self.score = None


class OddsScraper(BaseScraper):

    def __init__(self):
        super().__init__()

    def scrape_year(self, contest, contest_round):

        # EurovisionWorld changed the URL structure for the current contest
        if contest.year == 2026:

            if contest_round == "final":
                url = "https://eurovisionworld.com/odds/eurovision-2026"

            elif contest_round == "semi-final-1":
                url = "https://eurovisionworld.com/odds/eurovision-semi-final-1"

            elif contest_round == "semi-final-2":
                url = "https://eurovisionworld.com/odds/eurovision-semi-final-2"

            else:
                return contest

        else:

            if contest_round == "final":
                url = f"https://eurovisionworld.com/odds/eurovision-{contest.year}"
            else:
                url = f"https://eurovisionworld.com/odds/eurovision-{contest.year}-{contest_round}"

        print(f"Fetching {url}")

        html = self.get_html_via_flaresolverr(url)

        if not html:
            print("Failed to retrieve page.")
            return contest

        self.soup = BeautifulSoup(html, "html.parser")

        odds_table = self.soup.find("div", class_="odds_div")

        if odds_table is None:
            print(f"No odds table found for {contest.year} {contest_round}")
            return contest

        betting_offices = []

        headers = odds_table.find_all("th")

        for h in headers:

            if h.has_attr("data-bm") and h.has_attr("data-sc"):

                betting_offices.append(
                    BettingOffice(
                        bm_id=int(h["data-bm"]),
                        sc_id=int(h["data-sc"]),
                        name=h.get_text(strip=True)
                    )
                )

        tbody = odds_table.find("tbody")

        if tbody is None:
            print("No table body found.")
            return contest

        rows = tbody.find_all("tr")

        print(f"Found {len(rows)} contestants.")

        for row in rows:

            cols = row.find_all("td")

            try:

                if contest.year < 2017:
                    _, country_artist = cols[:2]
                    betting_cols = cols[2:]

                elif contest.year == 2017:
                    _, _, country_artist = cols[:3]
                    betting_cols = cols[3:]

                else:
                    _, _, country_artist, _ = cols[:4]
                    betting_cols = cols[4:]

                if len(betting_cols) != len(betting_offices):
                    print("Skipping row because bookmaker count does not match.")
                    continue

                country_name = country_artist.find_next(string=True).strip()

                country = contest.add_country_to_contest(
                    country_name,
                    country_name
                )

                span = country_artist.find("span")

                if span is None:
                    continue

                artist_song = span.get_text(strip=True)

                if " - " not in artist_song:
                    continue

                artist, song = artist_song.split(" - ", 1)

                link = country_artist.find("a")
                page_url = link.get("href", "") if link else ""

                contestant = contest.add_contestant_to_contest(
                    contest_round,
                    country,
                    artist,
                    song,
                    page_url
                )

                for office, score_cell in zip(betting_offices, betting_cols):

                    office_copy = deepcopy(office)

                    score = score_cell.get_text(strip=True)

                    if score == "":
                        office_copy.score = None
                    else:
                        try:
                            office_copy.score = float(score)
                        except ValueError:
                            office_copy.score = None

                    contestant.betting_offices.append(office_copy)

            except Exception as e:

                print("Skipping malformed row.")
                print(e)

        print(f"Finished {contest.year} {contest_round}")

        return contest