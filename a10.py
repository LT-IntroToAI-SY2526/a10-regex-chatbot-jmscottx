import re, string, requests, time
from bs4 import BeautifulSoup
from match import match
from typing import List, Callable, Tuple, Any, Match


def get_page_html(title: str) -> str:
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
                time.sleep(2)
                return data["parse"]["text"]["*"]
    raise ConnectionError(f"Could not retrieve Wikipedia page for '{title}' after 5 attempts")


def get_first_infobox_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    results = soup.find_all(class_="infobox")

    if not results:
        raise LookupError("Page has no infobox")
    return results[0].text


def clean_text(text: str) -> str:
    only_ascii = "".join([char if char in string.printable else " " for char in text])
    no_dup_spaces = re.sub(" +", " ", only_ascii)
    no_dup_newlines = re.sub("\n+", "\n", no_dup_spaces)
    return no_dup_newlines


def get_match(text: str, pattern: str, error_text: str) -> Match:
    p = re.compile(pattern, re.DOTALL | re.IGNORECASE)
    match = p.search(text)
    if not match:
        raise AttributeError(error_text)
    return match


# -----------------------------
#  EXISTING FUNCTIONS
# -----------------------------

def get_polar_radius(planet_name: str) -> str:
    infobox_text = clean_text(get_first_infobox_text(get_page_html(planet_name)))
    pattern = r"(?:Polar radius|Mean radius)[^\d]*(?P<radius>[\d,.]+).*?km"
    match = get_match(infobox_text, pattern, "Page infobox has no polar radius information")
    return match.group("radius")


def get_birth_date(name: str) -> str:
    infobox_text = clean_text(get_first_infobox_text(get_page_html(name)))
    pattern = r"Born\D*(?P<birth>\d{4}-\d{2}-\d{2})"
    match = get_match(infobox_text, pattern, "Page infobox has no birth date")
    return match.group("birth")


# -----------------------------
#  NEW FUNCTIONS (3 required)
# -----------------------------

def get_population(place: str) -> str:
    infobox_text = clean_text(get_first_infobox_text(get_page_html(place)))
    pattern = r"Population[^\d]*(?P<pop>[\d,]+)"
    match = get_match(infobox_text, pattern, "Page infobox has no population info")
    return match.group("pop")


def get_capital(country: str) -> str:
    infobox_text = clean_text(get_first_infobox_text(get_page_html(country)))
    pattern = r"Capital[^\n]*\n(?P<cap>[^\n]+)"
    match = get_match(infobox_text, pattern, "Page infobox has no capital info")
    return match.group("cap").strip()


def get_height(person: str) -> str:
    infobox_text = clean_text(get_first_infobox_text(get_page_html(person)))
    pattern = r"Height[^\d]*(?P<height>[\d.]+ ?m)"
    match = get_match(infobox_text, pattern, "Page infobox has no height info")
    return match.group("height")


# -----------------------------
#  ACTION FUNCTIONS
# -----------------------------

def birth_date(matches: List[str]) -> List[str]:
    return [get_birth_date(" ".join(matches))]


def polar_radius(matches: List[str]) -> List[str]:
    return [get_polar_radius(matches[0])]


def population(matches: List[str]) -> List[str]:
    return [get_population(" ".join(matches))]


def capital_city(matches: List[str]) -> List[str]:
    return [get_capital(" ".join(matches))]


def height(matches: List[str]) -> List[str]:
    return [get_height(" ".join(matches))]


def bye_action(dummy: List[str]) -> None:
    raise KeyboardInterrupt


# -----------------------------
#  PATTERN–ACTION LIST
# -----------------------------

Pattern = List[str]
Action = Callable[[List[str]], List[Any]]

pa_list: List[Tuple[Pattern, Action]] = [
    ("when was % born".split(), birth_date),
    ("what is the birth date of %".split(), birth_date),

    ("what is the polar radius of %".split(), polar_radius),

    ("what is the population of %".split(), population),
    ("how many people live in %".split(), population),

    ("what is the capital of %".split(), capital_city),

    ("how tall is %".split(), height),
    ("what is the height of %".split(), height),

    (["bye"], bye_action),
]


# -----------------------------
#  QUERY LOOP
# -----------------------------

def search_pa_list(src: List[str]) -> List[str]:
    for pat, act in pa_list:
        mat = match(pat, src)
        if mat is not None:
            answer = act(mat)
            return answer if answer else ["No answers"]
    return ["I don't understand"]


def query_loop() -> None:
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


query_loop()