import requests
import pdfplumber
import io
import pandas as pd
import re

def scrape_espn_2025_pdf(pdf_url: str) -> pd.DataFrame:
    """
    Downloads and parses the 2025 ESPN PPR 300 PDF Cheat Sheet.
    """
    print(f"Downloading 2025 ESPN PDF from: {pdf_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(pdf_url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to download PDF: {e}")
        return pd.DataFrame()

    extracted_players = []

    # Open the PDF directly from memory
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        for page_number, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')
            if page_number == 0:
                print(f"\n--- First 20 lines of page 1 ---")
                for i, l in enumerate(lines[:20]):
                    print(f"{i+1}: {l}")
            for line in lines:
                # Find all player entries in the line, and try to extract bye week after auction value
                # Example: 1. (WR1) Ja'Marr Chase, CIN $57 10 81. (RB28) Jaylen Warren, PIT $4 5 ...
                player_pattern = r"(\d+)\. \(([^)]+)\) ([^,]+), ([A-Z]{2,3}) \$(\d+) (\d{1,2})"
                for match in re.findall(player_pattern, line):
                    overall_rank, position_rank, player_name, team, auction_value, bye_week = match
                    # Extract position (e.g., 'WR' from 'WR1')
                    position = re.match(r"[A-Z]+", position_rank)
                    position = position.group(0) if position else None
                    # Ensure position_rank is always an integer for DB
                    from etl.transform.normalize import extract_position_rank
                    extracted_players.append({
                        'source_name': 'ESPN_PDF',
                        'scraped_player_name': player_name.strip(),
                        'team': team,
                        'position_rank': extract_position_rank(position_rank),
                        'position': position,
                        'overall_rank': int(overall_rank),
                        'auction_value': int(auction_value),
                        'bye_week': int(bye_week)
                    })

    # Convert to a DataFrame
    df = pd.DataFrame(extracted_players)
    # Remove duplicates based on all relevant columns
    if not df.empty:
        df = df.drop_duplicates(subset=[
            'scraped_player_name', 'team', 'position_rank', 'overall_rank', 'auction_value'
        ])
        df = df.sort_values(by='overall_rank').reset_index(drop=True)
    return df

# --- Testing the Script ---
if __name__ == "__main__":
    # The 2025 URL you provided
    url_2025 = "https://g.espncdn.com/s/ffldraftkit/25/NFL25_CS_PPR300.pdf?adddata=2025CS_PPR300"
    
    espn_2025_df = scrape_espn_2025_pdf(url_2025)
    
    if not espn_2025_df.empty:
        print("\n--- Successfully Scraped 2025 PDF ---")
        print(f"Total Players Extracted: {len(espn_2025_df)}")
        print("\nTop 5 Players:")
        print(espn_2025_df.head())
    else:
        print("\nFailed to extract players. ESPN may have changed their PDF formatting.")
