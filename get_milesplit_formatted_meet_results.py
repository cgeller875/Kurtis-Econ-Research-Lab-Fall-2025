import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re

# Constants
INDIVIDUAL_TABLE_HEADERS = ['place', 'video', 'athlete', 'grade', 'team', 'finish', 'point']
TEAM_TABLE_HEADERS = ['place', 'tsTeam', 'point', 'wind', 'heat']

# Function to extract the race ID from the URL
def extract_race_id(url):
    match = re.search(r'results/(\d+)/', url)
    return match.group(1) if match else None

# Function to extract table data from the page content
def extract_table_data(page_content, url):
    race_id = extract_race_id(url)
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

# Function to process URLs and save data
def process_urls_and_save(urls):
    individual_results = pd.DataFrame()
    team_results = pd.DataFrame()
    metadata_results = pd.DataFrame()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, 
            executable_path="C:\Program Files\Google\Chrome\Application\chrome.exe")
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