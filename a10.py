import json
import re, string, calendar, requests, time
from bs4 import BeautifulSoup
from match import match
from typing import List, Callable, Tuple, Any, Match


def get_page_html(title: str) -> str:
    search_response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "list": "search", "srsearch": title, "format": "json"},
        headers={"User-Agent": "intro-ai-class/1.0"},
        timeout=10
    )
    results = search_response.json().get("query", {}).get("search", [])
    if results:
        title = results[0]["title"]  # use the top search result title
        print(f"Searching Wikipedia for: {title}")
    
    for attempt in range(5):
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "parse",
                "page": title,
                "prop": "text",
                "format": "json",
                "redirects": True,
            },
            headers={"User-Agent": "intro-ai-class/1.0"}
        )
        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", 5))
            print(f"Rate limited — waiting {wait}s before retrying '{title}'...")
            time.sleep(wait)
            continue
        if response.status_code == 200 and response.text.strip():
            data = response.json()
            if "error" not in data:
                time.sleep(2)  # polite delay after every successful call
                return data["parse"]["text"]["*"]
    raise ConnectionError(f"Could not retrieve Wikipedia page for '{title}' after 5 attempts")


def get_first_infobox_text(html: str) -> str:
    """Gets first infobox html from a Wikipedia page (summary box)

    Args:
        html - the full html of the page

    Returns:
        html of just the first infobox
    """
    soup = BeautifulSoup(html, "html.parser")
    results = soup.find_all(class_="infobox")

    if not results:
        raise LookupError("Page has no infobox")
    return results[0].text


def clean_text(text: str) -> str:
    """Cleans given text removing non-ASCII characters and duplicate spaces & newlines

    Args:
        text - text to clean

    Returns:
        cleaned text
    """
    only_ascii = "".join([char if char in string.printable else " " for char in text])
    no_dup_spaces = re.sub(" +", " ", only_ascii)
    no_dup_newlines = re.sub("\n+", "\n", no_dup_spaces)
    return no_dup_newlines


def get_match(
    text: str,
    pattern: str,
    error_text: str = "Page doesn't appear to have the property you're expecting",
) -> Match:
    """Finds regex matches for a pattern

    Args:
        text - text to search within
        pattern - pattern to attempt to find within text
        error_text - text to display if pattern fails to match

    Returns:
        text that matches
    """
    p = re.compile(pattern, re.DOTALL | re.IGNORECASE)
    match = p.search(text)

    if not match:
        raise AttributeError(error_text)
    return match


def get_polar_radius(planet_name: str) -> str:
    """Gets the radius of the given planet

    Args:
        planet_name - name of the planet to get radius of

    Returns:
        radius of the given planet
    """
    infobox_text = clean_text(get_first_infobox_text(get_page_html(planet_name)))
    pattern = r"(?:Polar radius|Mean radius)(?:[^\d]*)(?P<radius>[\d,.]+)(?:.*?)km"
    error_text = "Page infobox has no polar radius information"
    match = get_match(infobox_text, pattern, error_text)

    return match.group("radius")


def get_birth_date(name: str) -> str:
    """Gets birth date of the given person

    Args:
        name - name of the person

    Returns:
        birth date of the given person
    """
    infobox_text = clean_text(get_first_infobox_text(get_page_html(name)))
    pattern = r"(?:Born\D*)(?P<birth>\d{4}-\d{2}-\d{2})"
    error_text = (
        "Page infobox has no birth information (at least none in xxxx-xx-xx format)"
    )
    match = get_match(infobox_text, pattern, error_text)

    return match.group("birth")

def get_official_language(place: str) -> str:
    """Gets the official language of the given place"""
    search_term = place.strip().title()
    html = get_page_html(search_term)
    infobox_text = clean_text(get_first_infobox_text(html))
    #print(infobox_text)
    
    # Regex looks for "Official language" followed by the first word(s)
    # until it hits a newline or a bracketed reference.
    pattern =r"Official\s+languages?\s*(?P<lang>[A-Z][a-z]+)"
    error_text = f"I found the page for {search_term}, but couldn't identify the official language."
    
    match_obj = get_match(infobox_text, pattern, error_text)
    return match_obj.group("lang").strip()

def get_capital_city(place: str) -> str:
    """Gets capital city of a state/country."""

    html = get_page_html(place)

    soup = BeautifulSoup(html, "html.parser")

    infobox = soup.find("table", class_=lambda x: x and "infobox" in x)

    if not infobox:
        return "Capital city not found"

    rows = infobox.find_all("tr")

    for row in rows:

        header = row.find("th")

        if header and "capital" in header.get_text().lower():

            td = row.find("td")

            if td:

                text = td.get_text(" ", strip=True)

                text = re.sub(r"\[\d+\]", "", text)

                words = text.split()

                if words:
                    return words[0]

    return "Capital city not found"

# below are a set of actions. Each takes a list argument and returns a list of answers
# according to the action and the argument. It is important that each function returns a
# list of the answer(s) and not just the answer itself.

# ==========================================
# NEW FEATURE: CITY & STATE OF A COLLEGE
# ==========================================

def get_college_location(college: str) -> str:

    infobox = clean_text(get_first_infobox_text(get_page_html(college)))

    pattern = r"Location\s*(?P<loc>[A-Za-z .'-]+,\s*[A-Za-z .'-]+)"

    match = get_match(
        infobox,
        pattern,
        "Location not found"
    )

    return match.group("loc").strip()


def college_location(matches):
    return [get_college_location(" ".join(matches))]


# ==========================================
# NEW FEATURE: RELEASE DATE OF ALBUM
# ==========================================

def get_album_release(album: str):
    # Force Wikipedia to search for the album page
    html = get_page_html(album + " album")
    infobox = clean_text(get_first_infobox_text(html))

    pattern = (
        r"(Released|Release date)\s*"
        r"(?P<date>[A-Za-z]+\s+\d{1,2},\s*\d{4}|[A-Za-z]+\s+\d{4})"
    )

    match = re.search(pattern, infobox, re.IGNORECASE)
    return match.group("date") if match else "Release date not found"





# ==========================================
# NEW FEATURE: MOST POPULAR SONG
# ==========================================

def get_most_popular_song(artist: str) -> str:
    # External-first fallback: Last.fm top tracks page (often lists popular tracks without an API)
    try:
        slug = re.sub(r"[^A-Za-z0-9 ]", "", artist).strip().replace(" ", "+")
        url = f"https://www.last.fm/music/{slug}/+tracks"
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
            },
            timeout=10,
        )
        if resp.status_code == 200 and resp.text:
            soup_l = BeautifulSoup(resp.text, "html.parser")
            td = soup_l.find("td", class_="chartlist-name")
            if td:
                a = td.find("a")
                if a:
                    title = a.get("title") or a.get_text(strip=True)
                    if title:
                        return re.sub(r"\[\d+\]", "", title).strip()
    except Exception:
        pass

    # Try the main artist page first and look in the infobox for "Notable" entries
    html_main = ""
    disc_html = ""
    try:
        html_main = get_page_html(artist)
        soup = BeautifulSoup(html_main, "html.parser")
        infobox = soup.find("table", class_=lambda x: x and "infobox" in x)
        if infobox:
            for row in infobox.find_all("tr"):
                header = row.find("th")
                if header:
                    htext = header.get_text(" ", strip=True).lower()
                    if "notable" in htext or "notable works" in htext or "notable singles" in htext or "notable songs" in htext:
                        td = row.find("td")
                        if td:
                            # prefer the first linked title
                            a = td.find("a")
                            if a and a.get_text(strip=True):
                                return re.sub(r"\[\d+\]", "", a.get_text(strip=True))
                            # otherwise use plain text and split on common separators
                            txt = clean_text(td.get_text(" ", strip=True))
                            first = re.split(r";|,|\n", txt)[0]
                            first = re.sub(r"\s*\(.*?\)", "", first)
                            first = re.sub(r"\[\d+\]", "", first).strip()
                            if first:
                                return first
    except Exception:
        pass

    # Scan paragraphs and list items on the main page for mentions of 'single' and return a linked title
    try:
        if html_main:
            soup_main = BeautifulSoup(html_main, "html.parser")
            # First, look in the lead paragraph(s) for quoted song titles or first sensible links
            parser_output = soup_main.find("div", class_="mw-parser-output") or soup_main
            for p in parser_output.find_all("p", recursive=False):
                ptext = p.get_text(" ", strip=True)
                # look for quoted titles
                m = re.search(r"[“\"'‘](?P<title>[A-Z][^\"’”']{2,80})[”\"'’]", ptext)
                if m:
                    return m.group("title").strip()
                for a in p.find_all("a"):
                    txt = a.get_text(strip=True)
                    href = a.get("href", "")
                    title_attr = a.get("title", "")
                    txt_lower = txt.lower()
                    # Prefer links that explicitly look like song pages (title attribute contains 'song'/'single')
                    if title_attr and ("(song" in title_attr.lower() or "(single" in title_attr.lower()):
                        return re.sub(r"\[\d+\]", "", txt)
                    # Heuristic: link text that looks like a song title (Capitalized, more than one word,
                    # not the artist name and not a generic descriptor)
                    if href.startswith("/wiki/") and txt and txt[0].isupper() and txt.count(" ") >= 1:
                        bad_words = ("born", "american", "british", "band", "group", "singer", "composer", "album", "discography")
                        if not any(b in txt_lower for b in bad_words) and not txt_lower.startswith(artist.lower()):
                            return re.sub(r"\[\d+\]", "", txt)

            # Fallback: scan paragraphs and list items for mentions of 'single' and return a linked title
            for tag in soup_main.find_all(["p", "li"]):
                txt = tag.get_text(" ", strip=True).lower()
                if "single" in txt:
                    for a in tag.find_all("a"):
                        title_attr = a.get("title", "")
                        txt_a = a.get_text(strip=True)
                        if title_attr and ("(song" in title_attr.lower() or "(single" in title_attr.lower()):
                            return re.sub(r"\[\d+\]", "", txt_a)
                        if txt_a and txt_a[0].isupper() and txt_a.count(" ") >= 1:
                            return re.sub(r"\[\d+\]", "", txt_a)
    except Exception:
        pass

    # Next try the artist's discography page and look for a Singles section
    try:
        disc_html = get_page_html(artist + " discography")
        soup = BeautifulSoup(disc_html, "html.parser")
        for header_tag in soup.find_all(["h2", "h3"]):
            header_text = header_tag.get_text(" ", strip=True).lower()
            if "singles" in header_text:
                # search following siblings for a list or table; also look inside wrapper tags
                sib = None
                for sibling in header_tag.next_siblings:
                    if getattr(sibling, "name", None) and sibling.name in ("h2", "h3"):
                        break
                    if getattr(sibling, "name", None) and sibling.name in ("ul", "ol", "table"):
                        sib = sibling
                        break
                    if hasattr(sibling, "find"):
                        inner = sibling.find(["ul", "ol", "table"])
                        if inner:
                            sib = inner
                            break
                if not sib:
                    continue
                if sib.name in ("ul", "ol"):
                    li = sib.find("li")
                    if li:
                        a = li.find("a")
                        if a and a.get_text(strip=True):
                            return re.sub(r"\[\d+\]", "", a.get_text(strip=True))
                        return re.sub(r"\[\d+\]", "", clean_text(li.get_text(" ", strip=True))).strip()
                if sib.name == "table":
                    # Try to locate a 'Title' column header and use that column's first data row.
                    headers = sib.find_all('th')
                    title_col = None
                    for idx, th in enumerate(headers):
                        if 'title' in th.get_text(" ", strip=True).lower():
                            title_col = idx
                            break

                    rows = sib.find_all('tr')
                    data_rows = [r for r in rows if r.find_all('td')]

                    if title_col is not None:
                        for r in data_rows:
                            cells = r.find_all(['td', 'th'])
                            if len(cells) > title_col:
                                cell = cells[title_col]
                                a = cell.find('a')
                                if a and a.get_text(strip=True):
                                    return re.sub(r"\[\d+\]", "", a.get_text(strip=True))
                                text = clean_text(cell.get_text(" ", strip=True))
                                text = re.sub(r"\[\d+\]", "", text).strip()
                                if text:
                                    return text

                    # Fallback: find the first reasonable link in data rows (avoid links to other discography pages)
                    for r in data_rows:
                        for a in r.find_all('a'):
                            txt = a.get_text(strip=True)
                            href = a.get('href', '')
                            if txt and href.startswith('/wiki/') and 'discography' not in href and 'album' not in href:
                                return re.sub(r"\[\d+\]", "", txt)

                    first_td = sib.find('td')
                    if first_td:
                        return re.sub(r"\[\d+\]", "", clean_text(first_td.get_text(" ", strip=True))).strip()
    except Exception:
        pass

    # Last resort: search raw text for quoted titles near the word 'single'
    combined = clean_text((disc_html or "") + "\n" + (html_main or ""))
    m = re.search(r"[\"'](?P<title>[A-Z][A-Za-z0-9 &'\-,:.!?]+?)[\"'](?=[\s\S]{0,120}?single)", combined)
    if m:
        return m.group("title").strip()

    # (Last.fm attempt already tried at the top)

    return "Popular song not found"

# ==========================================
# NEW FEATURE: ACCEPTANCE RATE
# ==========================================

def get_acceptance_rate(college: str) -> str:
    html = get_page_html(college)
    # try infobox first (more structured)
    try:
        infobox = clean_text(get_first_infobox_text(html))
    except Exception:
        infobox = ""

    # Prefer parsing the infobox table for a dedicated acceptance/admissions row
    try:
        soup = BeautifulSoup(html, "html.parser")
        infobox_table = soup.find("table", class_=lambda x: x and "infobox" in x)
        if infobox_table:
            for row in infobox_table.find_all("tr"):
                header = row.find("th")
                if header and ("accept" in header.get_text().lower() or "admiss" in header.get_text().lower()):
                    td = row.find("td")
                    if td:
                        td_text = clean_text(td.get_text(" ", strip=True))
                        mtd = re.search(r"(?P<rate>\d{1,3}(?:\.\d+)?\s*(?:%|percent))", td_text)
                        if mtd:
                            return mtd.group("rate").replace("percent", "%").strip()
    except Exception:
        pass

    text = clean_text(html)

    # Broader patterns to match variants like:
    # "acceptance rate 3.4%", "admissions rate was 4 percent", "acceptance: 8.4% (2022)"
    # require the word 'rate' near 'acceptance' or 'admission' to avoid matching other
    # admission-related percentages such as yield rates
    patterns = [
        r"(?:acceptance|admission)s?\s*(?:rate|rates|percentage)[^\n%]{0,80}(?P<rate>\d{1,3}(?:\.\d+)?\s*(?:%|percent))",
        r"(?P<rate>\d{1,3}(?:\.\d+)?\s*(?:%|percent))\s*(?:acceptance|admission)s?\s*(?:rate|rates)?",
    ]

    for p in patterns:
        m = re.search(p, infobox, re.IGNORECASE)
        if m:
            return m.group("rate").replace("percent", "%").strip()

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group("rate").replace("percent", "%").strip()

    # fallback: any nearby percent number with 'accept' or 'admiss' within a small window
    m = re.search(r"(?P<rate>\d{1,3}(?:\.\d+)?\s*%)", text)
    if m:
        window = text[max(0, m.start() - 80) : m.end() + 80].lower()
        if "accept" in window or "admiss" in window:
            return m.group("rate").strip()

    # If we couldn't find a structured acceptance/admission percentage on Wikipedia,
    # fall back to reporting not found. External site fallbacks were removed to avoid
    # unreliable network/timeouts in this environment.
    return "Acceptance rate not found"




# ==========================================
# NEW FEATURE: NFL COACH
# ==========================================

def get_nfl_coach(team):

    infobox = clean_text(get_first_infobox_text(get_page_html(team)))

    pattern = r"(?:Head coach)\s*(?P<coach>[A-Za-z .'-]+)"

    match = get_match(
        infobox,
        pattern,
        "Coach not found"
    )

    return match.group("coach").strip()


def nfl_coach(matches):
    return [get_nfl_coach(" ".join(matches))]


def birth_date(matches: List[str]) -> List[str]:
    """Returns birth date of named person in matches

    Args:
        matches - match from pattern of person's name to find birth date of

    Returns:
        birth date of named person
    """
    return [get_birth_date(" ".join(matches))]


def polar_radius(matches: List[str]) -> List[str]:
    """Returns polar radius of planet in matches

    Args:
        matches - match from pattern of planet to find polar radius of

    Returns:
        polar radius of planet
    """
    return [get_polar_radius(matches[0])]

def get_birth_place(name: str) -> str:
    infobox_text = clean_text(get_first_infobox_text(get_page_html(name)))

    pattern = r"Born.*?\d{4}[^\w]*([A-Za-z .'-]+,[A-Za-z .'-]+)"
    match = re.search(pattern, infobox_text)

    if match:
        return match.group(1).strip()

    pattern2 = r"Born[\s\S]*?\(age \d+\)\s*([A-Za-z .'-]+,[A-Za-z .'-]+)(?=Afghanistan|Albania|Algeria|Andorra|Angola|Antigua|Argentina|Armenia|Australia|Austria|Azerbaijan|Baden|Bahamas|Bahrain|Bangladesh|Barbados|Bavaria|Belarus|Belgium|Belize|Benin|Bolivia|Bosnia|Botswana|Brazil|Brunei|Brunswick|Bulgaria|Burkina|Burma|Burundi|Cabo|Cambodia|Cameroon|Canada|Cayman|Central|Chad|Chile|China|Colombia|Comoros|Congo|Cook|Costa|Cote|Croatia|Cuba|Cyprus|Czechia|Czechoslovakia|Democratic|Denmark|Djibouti|Dominica|Dominican|Duchy|East|Ecuador|Egypt|El|Equatorial|Eritrea|Estonia|Eswatini|Ethiopia|Federal|Fiji|Finland|France|Gabon|Gambia|Georgia|Germany|Ghana|Grand|Greece|Grenada|Guatemala|Guinea|Guyana|Haiti|Hanover|Hanseatic|Hawaii|Hesse|Holy|Honduras|Hungary|Iceland|India|Indonesia|Iran|Iraq|Ireland|Israel|Italy|Jamaica|Japan|Jordan|Kazakhstan|Kenya|Kingdom|Kiribati|Korea|Kosovo|Kuwait|Kyrgyzstan|Laos|Latvia|Lebanon|Lesotho|Lew|Liberia|Libya|Liechtenstein|Lithuania|Luxembourg|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|Marshall|Mauritania|Mauritius|Mecklenburg-Schwerin|Mecklenburg-Strelitz|Mexico|Micronesia|Moldova|Monaco|Mongolia|Montenegro|Morocco|Mozambique|Namibia|Nassau|Nauru|Nepal|Netherlands|New|Nicaragua|Niger|Nigeria|Niue|North|Norway|Oldenburg|Oman|Orange|Pakistan|Palau|Panama|Papal|Papua|Paraguay|Peru|Philippines|Piedmont-Sardinia|Poland|Portugal|Qatar|Republic|Romania|Russia|Rwanda|Saint|Samoa|San|Sao|Saudi|Schaumburg-Lippe|Senegal|Serbia|Seychelles|Sierra|Singapore|Slovakia|Slovenia|Solomon|Somalia|South|Spain|Sri|Sudan|Suriname|Sweden|Switzerland|Syria|Tajikistan|Tanzania|Texas|Thailand|Timor-Leste|Togo|Tonga|Trinidad|Tunisia|Turkey|Turkmenistan|Tuvalu|Two|Uganda|Ukraine|Union|United|Uruguay|Uzbekistan|Vanuatu|Venezuela|Vietnam|Württemberg|Yemen|Zambia|Zimbabwe)"
    match2 = re.search(pattern2, infobox_text)
    if match2:
        birthplace = match2.group(1).strip()
        return birthplace
    

    return "Unknown"

def birth_place(matches):
    
    return [get_birth_place(" ".join(matches))]


def official_language(matches: List[str]) -> List[str]:
    """Action function for the official language query."""
    return [get_official_language(" ".join(matches))]

# dummy argument is ignored and doesn't matter
def bye_action(dummy: List[str]) -> None:
    raise KeyboardInterrupt

def album_release(matches):
    return [get_album_release(" ".join(matches))]

def popular_song(matches):
    return [get_most_popular_song(" ".join(matches))]

def acceptance_rate(matches):
    return [get_acceptance_rate(" ".join(matches))]


# type aliases to make pa_list type more readable, could also have written:
# pa_list: List[Tuple[List[str], Callable[[List[str]], List[Any]]]] = [...]
Pattern = List[str]
Action = Callable[[List[str]], List[Any]]

# The pattern-action list for the natural language query system. It must be declared
# here, after all of the function definitions
pa_list = [

    ("when was % born".split(), birth_date),

    ("what is the polar radius of %".split(), polar_radius),

    ("where was % born".split(), birth_place),

    ("what language do they speak in %".split(), official_language),

    # NEW FEATURES

    ("what city and state is % in".split(),
     college_location),

    ("when was % released".split(),
     album_release),

    ("what is the most popular song by %".split(),
     popular_song),

    ("what is the acceptance rate of %".split(),
     acceptance_rate),

    ("who is the coach of %".split(),
     nfl_coach),

    (["bye"], bye_action),
]



def search_pa_list(src: List[str]) -> List[str]:
    """Takes source, finds matching pattern and calls corresponding action. If it finds
    a match but has no answers it returns ["No answers"]. If it finds no match it
    returns ["I don't understand"].

    Args:
        source - a phrase represented as a list of words (strings)

    Returns:
        a list of answers. Will be ["I don't understand"] if it finds no matches and
        ["No answers"] if it finds a match but no answers
    """
    for pat, act in pa_list:
        mat = match(pat, src)
        if mat is not None:
            answer = act(mat)
            return answer if answer else ["No answers"]

    return ["I don't understand"]


def query_loop() -> None:
    """The simple query loop. The try/except structure is to catch Ctrl-C or Ctrl-D
    characters and exit gracefully"""
    print("Welcome to the wikipedia chatbot!\n")
    while True:
        try:
            print()
            query = input("Your query? ").replace("?", "").lower().split()
            answers = search_pa_list(query)
            for ans in answers:
                print(ans)

        except (KeyboardInterrupt, EOFError):
            break

    print("\nSo long!\n")


# uncomment the next line once you've implemented everything are ready to try it out. death date, off. language, birthplace
query_loop()