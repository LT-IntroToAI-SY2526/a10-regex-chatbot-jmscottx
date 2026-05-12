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

def get_death_date(name: str) -> str:
    html = get_page_html(name)
    if html.startswith("ERROR"):
        return html  # return the error message directly

    infobox_text = clean_text(get_first_infobox_text(html))

    pattern = (
        r"(?:Died\D*)"
        r"(?P<death>"
        r"\d{4}-\d{2}-\d{2}"
        r"|[A-Za-z]+ \d{1,2}, \d{4}"
        r"|\d{1,2} [A-Za-z]+ \d{4}"
        r")"
    )

    match = re.search(pattern, infobox_text, re.IGNORECASE)
    if not match:
        return "Death date not found"

    return match.group("death")


def get_population(place: str) -> str:
    """Gets population of a city/country safely and robustly."""
    html = get_page_html(place)

    # Handle network or API errors
    if html.startswith("ERROR"):
        return html

    try:
        infobox_text = clean_text(get_first_infobox_text(html))
    except Exception:
        return "Population not found"

    # Match first population number after any 'Population' label
    pattern = r"Population[^0-9]+(?P<pop>[0-9][0-9,]*)"
    match = re.search(pattern, infobox_text, re.IGNORECASE)

    if not match:
        return "Population not found"

    return match.group("pop")


def get_capital_city(country: str) -> str:
    """Gets the capital city of a country safely and robustly."""
    html = get_page_html(country)

    # Handle network or API errors
    if html.startswith("ERROR"):
        return html

    try:
        infobox_text = clean_text(get_first_infobox_text(html))
    except Exception:
        return "Capital city not found"

    # Capture text after "Capital" up to newline
    pattern = r"Capital[^A-Za-z]+(?P<cap>[A-Za-z ,()]+)"
    match = re.search(pattern, infobox_text, re.IGNORECASE)

    if not match:
        return "Capital city not found"

    capital = match.group("cap").strip()

    # Remove parentheses like "(executive)"
    capital = re.sub(r"\([^)]*\)", "", capital).strip()

    # If multiple capitals listed, return the first
    if "," in capital:
        capital = capital.split(",")[0].strip()

    return capital


# below are a set of actions. Each takes a list argument and returns a list of answers
# according to the action and the argument. It is important that each function returns a
# list of the answer(s) and not just the answer itself.


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

def death_date(matches: List[str]) -> List[str]:
    name = " ".join(matches).strip()
    result = get_death_date(name)
    return [result]

def population(matches: List[str]) -> List[str]:
    place = " ".join(matches).strip()
    result = get_population(place)
    return [result]

def capital_city(matches: List[str]) -> List[str]:
    country = " ".join(matches).strip()
    result = get_capital_city(country)
    return [result]


# dummy argument is ignored and doesn't matter
def bye_action(dummy: List[str]) -> None:
    raise KeyboardInterrupt


# type aliases to make pa_list type more readable, could also have written:
# pa_list: List[Tuple[List[str], Callable[[List[str]], List[Any]]]] = [...]
Pattern = List[str]
Action = Callable[[List[str]], List[Any]]

# The pattern-action list for the natural language query system. It must be declared
# here, after all of the function definitions
pa_list: List[Tuple[Pattern, Action]] = [
    ("when was % born".split(), birth_date),
    ("what is the polar radius of %".split(), polar_radius),

    # NEW FEATURES
    ("when did % die".split(), death_date),
    ("what is the population of %".split(), population),
    ("what is the capital of %".split(), capital_city),

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


# uncomment the next line once you've implemented everything are ready to try it out
query_loop()

