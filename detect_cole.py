import re
from bs4 import BeautifulSoup

def detect_cole(html_path: str) -> float:
    """
    Detect whether an HTML file matches Cole's results format.

    Args:
        html_path (str): Path to the HTML file.

    Returns:
        float: Confidence score in [0.0, 1.0]
            - 1.0 = definitely Cole's format
            - 0.0 = definitely not Cole's format

    Scoring breakdown:
        +0.6  Strong indicator: <pre> includes all expected headers
        +0.3  Secondary indicator: Results body contains <pre> blocks and no <table>
        +0.1  Weak indicator: No "Team Scores" section appears in <pre> blocks
    """

    # --- Define expected headers for Cole's format ---
    REQUIRED_HEADERS_COLE = {"pl", "athlete", "yr", "team", "time"}

    # --- Step 1: Load and parse the HTML ---
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print(f"Error: file not found → {html_path}")
        return 0.0

    soup = BeautifulSoup(html, "html.parser")
    score = 0.0

    # --- Step 2: Identify results container ---
    results_body = soup.find(id="meetResultsBody") or soup.find(class_="meetResultsBody")
    if not results_body:
        return 0.0  # definitely not Cole format

    pre_blocks = results_body.find_all("pre")
    table_blocks = results_body.find_all("table")

    # --- Step 3: Strong indicator — header presence ---
    for pre in pre_blocks:
        text = pre.get_text(" ", strip=True).lower()
        if all(h in text for h in REQUIRED_HEADERS_COLE):
            score += 0.6
            break  # only count once if found

    # --- Step 4: Secondary indicator — block type check ---
    if pre_blocks and not table_blocks:
        score += 0.3
    else:
        return 0.0  # stop early if structure doesn’t match

    # --- Step 5: Weak indicator — no "Team Scores" section ---
    found_team_scores = any("team scores" in pre.get_text().lower() for pre in pre_blocks)
    if not found_team_scores:
        score += 0.1

    return float(min(1.0,score))




#Change this base path to match your directory.
TEST_PATHS = {
    "Cole": r"C:\Users\coleg\OneDrive\Documents\Econ Research Lab\raw_html_files\meet_494231.html",
    "Adam": r"C:\Users\coleg\OneDrive\Documents\Econ Research Lab\raw_html_files\meet_493916.html",
    "Max": r"C:\Users\coleg\OneDrive\Documents\Econ Research Lab\raw_html_files\meet_44115.html",
    "Katie": r"C:\Users\coleg\OneDrive\Documents\Econ Research Lab\raw_html_files\Mission_Angelus League Clusters #2 2025 - Complete.html",
}

for name, path in TEST_PATHS.items():
    score = detect_cole(path)

    print(f"{name:6} format confidence score: {score:.2f}")
