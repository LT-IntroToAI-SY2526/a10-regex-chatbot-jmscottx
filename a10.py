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
    # Search for the artist's discography page
    html = get_page_html(artist + " discography")
    text = clean_text(html)

    # Look for a "Singles" section
    pattern = r"Singles\s*\n.*?\n(?P<song>[A-Za-z0-9 .'\-]+)"
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group("song").strip()

    # Backup: look for "Notable singles"
    pattern2 = r"Notable singles\s*\n.*?\n(?P<song>[A-Za-z0-9 .'\-]+)"
    match2 = re.search(pattern2, text, re.IGNORECASE)

    if match2:
        return match2.group("song").strip()

    return "Popular song not found"

# ==========================================
# NEW FEATURE: ACCEPTANCE RATE
# ==========================================

def get_acceptance_rate(college: str) -> str:
    html = get_page_html(college)
    text = clean_text(html)

    # Match formats like:
    # "acceptance rate 3.4%"
    # "acceptance rate was 4%"
    # "an acceptance rate of 5%"
    pattern = r"acceptance rate[^0-9]*(?P<rate>\d+\.?\d*\s*%)"

    match = re.search(pattern, text, re.IGNORECASE)
    return match.group("rate") if match else "Acceptance rate not found"




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