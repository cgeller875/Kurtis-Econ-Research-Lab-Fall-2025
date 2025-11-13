import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re
import os

# Constants
INDIVIDUAL_TABLE_HEADERS = ['place', 'video', 'athlete', 'grade', 'team', 'finish', 'point']
TEAM_TABLE_HEADERS = ['place', 'tsTeam', 'point', 'wind', 'heat']

# Function to extract the race ID from the URL
def extract_race_id(url):
    match = re.search(r'results/(\d+)/', url)
    return match.group(1) if match else None

# Function to extract table data from the page content
def extract_table_data(page_content, url):
    race_id = extraccheckt_race_id(url)
    soup = BeautifulSoup(page_content, 'html.parser')
    tables = soup.find_all('table')

    if not tables:
        print(f"No tables found for URL: {url}")
        return {"individual": pd.DataFrame(), "team": pd.DataFrame()}, pd.DataFrame()

    all_data = {"individual": [], "team": []}
    metadata = []

    for table_index, table in enumerate(tables):
        rows = table.find_all('tr')
        if not rows:
            metadata.append({
                "race_id": race_id,
                "url": url,
                "table_index": table_index + 1,
                "table_type": "empty",
                "row_count": 0
            })
            continue

        # Extract headers from the first row
        first_row = rows[1]
        headers = [cell.get('class', [None])[0] for cell in first_row.find_all('td')]

        # Determine the table type
        if all(header in INDIVIDUAL_TABLE_HEADERS for header in headers):
            table_type = "individual"
        elif all(header in TEAM_TABLE_HEADERS for header in headers):
            table_type = "team"
        else:
            metadata.append({
                "race_id": race_id,
                "url": url,
                "table_index": table_index + 1,
                "table_type": "unknown_headers",
                "row_count": len(rows) - 1
            })
            continue

        # Extract data from the rows
        for row in rows[1:]:  # Skip the header row
            cells = row.find_all('td')
            if len(cells) != len(headers):
                continue  # Skip rows with mismatched column counts

            row_data = {"race_id": race_id, "race_url": url}
            for header, cell in zip(headers, cells):
                row_data[header] = cell.text.strip()
                # Extract href if present
                link = cell.find('a')
                if link and link.get('href'):
                    row_data[f"{header}_url"] = link.get('href')

            all_data[table_type].append(row_data)

        # Add metadata for the current table
        metadata.append({
            "race_id": race_id,
            "url": url,
            "table_index": table_index + 1,
            "table_type": table_type,
            "row_count": len(rows) - 1
        })

    metadata_df = pd.DataFrame(metadata)
    return {
        "individual": pd.DataFrame(all_data["individual"]),
        "team": pd.DataFrame(all_data["team"])
    }, metadata_df

def detect_cole(html_content: str) -> float:
    """
    Detect whether HTML content matches Cole's results format.

    Args:
        html_content (str): Raw HTML string.

    Returns:
        float: Confidence score in [0,1]
    """

    REQUIRED_HEADERS_COLE = {"pl", "athlete", "yr", "team", "time"}

    soup = BeautifulSoup(html_content, "html.parser")
    score = 0.0

    # Identify results container
    results_body = soup.find(id="meetResultsBody") or soup.find(class_="meetResultsBody")
    if not results_body:
        return 0.0

    pre_blocks = results_body.find_all("pre")
    table_blocks = results_body.find_all("table")

    # Strong indicator — headers inside <pre>
    for pre in pre_blocks:
        text = pre.get_text(" ", strip=True).lower()
        if all(h in text for h in REQUIRED_HEADERS_COLE):
            score += 0.6
            break

    # Secondary indicator — pre blocks exist & no tables exist
    if pre_blocks and not table_blocks:
        score += 0.3
    else:
        return 0.0

    # Weak indicator — no "Team Scores" section
    found_team_scores = any("team scores" in pre.get_text().lower() for pre in pre_blocks)
    if not found_team_scores:
        score += 0.1

    return float(min(1.0, score))


def wrangle_cole(html_content, race_url=None):
    """
    Parse Cole-style pages (<pre> based format).
    Returns a DataFrame matching INDIVIDUAL_TABLE_HEADERS.
    """

    soup = BeautifulSoup(html_content, "html.parser")

    results_div = soup.find("div", id="meetResultsBody")
    if not results_div:
        return pd.DataFrame(columns=INDIVIDUAL_TABLE_HEADERS)

    pre = results_div.find("pre")
    if not pre:
        return pd.DataFrame(columns=INDIVIDUAL_TABLE_HEADERS)

    text = pre.get_text("\n", strip=True)
    lines = text.splitlines()

    # Lines starting with place #
    data_lines = [ln for ln in lines if re.match(r"^\s*\d+", ln)]

    rows = []
    for ln in data_lines:
        match = re.match(
            r"^\s*(\d+)\s+(.+?)\s+(\d+)?\s+(.+?)\s+(\d{1,2}:\d{2}\.\d)", ln
        )

        if not match:
            continue

        place = int(match.group(1))
        athlete = match.group(2).strip().title()
        grade = int(match.group(3)) if match.group(3) else pd.NA
        team = match.group(4).strip()
        finish = match.group(5)

        rows.append({
            "place": place,
            "video": None,
            "athlete": athlete,
            "grade": grade,
            "team": team,
            "finish": finish,
            "point": pd.NA
        })

    return pd.DataFrame(rows, columns=INDIVIDUAL_TABLE_HEADERS)


# Function to process URLs and save data
def process_urls_and_save(urls):
    individual_results = pd.DataFrame()
    team_results = pd.DataFrame()
    metadata_results = pd.DataFrame()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        # Open a new page
        page = browser.new_page()

        for url in urls:
            try:
                # Navigate to the URL
                page.goto(url)
                page.wait_for_selector("table", timeout = 7000)  # Wait for at least one table to load

                # Extract data
                html_content = page.content()
                
                data, metadata = extract_table_data(html_content, url)

                # Run detectors on html_content
                cole_score = detect_cole(html_content)
                adam_score = detect_adam(html_content)
                max_score = detect_max(html_content)

                scores = {"cole": cole_score, "adam": adam_score, "max": max_score}
                best_detector = max(scores, key=scores.get)
                best_score = scores[best_detector]

                print(f"{url} → Best detector: {best_detector} (score: {best_score})")

                # Route HTML to proper wrangler based on best detector
                wrangled_data = {"individual": pd.DataFrame(), "team": pd.DataFrame()}

                if best_detector == "cole" and best_score >= 0.7:
                    wrangled_df = wrangle_cole(html_content, url)
                    wrangled_data["individual"] = wrangled_df

                elif best_detector == "adam" and best_score >= 0.7:
                    wrangled_df = wrangle_adam(html_content, url)
                    # Adam code here
                    print("Adam format")

                elif best_detector == "max" and best_score >= 0.7:
                    wrangled_df = wrangle_max(html_content, url)
                    # Max code here
                    print("Max format")
            
                else:
                    print(f"Low confidence ({best_score:.2f}) - skipping {url}")
                    wrangled_data = {"individual": pd.DataFrame(), "team": pd.DataFrame()}

                # Append data to the respective DataFrames
                if not data["individual"].empty:
                    individual_results = pd.concat([individual_results, data["individual"]], ignore_index=True)
                if not data["team"].empty:
                    team_results = pd.concat([team_results, data["team"]], ignore_index=True)
                if not metadata.empty:
                    metadata_results = pd.concat([metadata_results, metadata], ignore_index=True)

            except Exception as e:
                print(f"Error processing URL {url}: {e}")
                metadata_results = pd.concat([metadata_results, pd.DataFrame([{
                    "race_id": extract_race_id(url),
                    "url": url,
                    "table_index": '',
                    "table_type": f'error - {e}',
                    "row_count": ''
                }])], ignore_index=True)

        browser.close()
    return individual_results, team_results, metadata_results


# TESTING first 3 race_url!!!

df = pd.read_csv(r"C:\Users\coleg\OneDrive\Documents\Econ Research Lab\Kurtis-Econ-Research-Lab-Fall-2025\race_urls_2016.0.csv")

subset = df.iloc[:3]
urls = subset["race_url"].tolist()

for url in urls:
    print(f"\nProcessing: {url}")

    indiv, team, meta = process_urls_and_save([url])

    race_id = extract_race_id(url)
    if race_id is None:
        race_id = url.split("/")[-2]

    output_dir = r"C:\Users\coleg\OneDrive\Documents\Econ Research Lab\Kurtis-Econ-Research-Lab-Fall-2025\output"

    indiv.to_csv(os.path.join(output_dir, f"individual_results_{race_id}.csv"), index=False)
    team.to_csv(os.path.join(output_dir, f"team_results_{race_id}.csv"), index=False)
    meta.to_csv(os.path.join(output_dir, f"metadata_results_{race_id}.csv"), index=False)

    print(f"✓ Saved individual_results_{race_id}.csv")
    print(f"✓ Saved team_results_{race_id}.csv")
    print(f"✓ Saved metadata_results_{race_id}.csv")