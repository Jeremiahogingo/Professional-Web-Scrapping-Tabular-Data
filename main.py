from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import os


def ensure_results_folder():
    """Create results folder if it doesn't exist and return the path."""
    folder_path = "results"
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"📁 Created folder: {folder_path}")
    return folder_path


def handle_consent_popup(driver):
    """Handle cookie consent popups if they appear."""
    try:
        # Common consent button selectors
        consent_selectors = [
            "button#acceptAll",
            "button#accept-cookies",
            "button#consent-accept", 
            "button.accept-cookies",
            "button.agree-button",
            "button[aria-label*='accept']",
            "button[aria-label*='Accept']",
            "button[onclick*='cookie']",
            ".cookie-consent button",
            ".cc-accept",
            ".consent-accept"
        ]
        
        for selector in consent_selectors:
            try:
                consent_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                consent_button.click()
                print("✅ Consent popup handled")
                time.sleep(1)  # Brief pause after clicking
                break
            except:
                continue
    except Exception as e:
        print(f"ℹ️ No consent popup found or couldn't handle it: {str(e)}")


def scrape_multiple_pages(base_url, pages, driver, base_filename="premier_league"):
    """Scrape multiple pages with pagination."""
    results_folder = ensure_results_folder()
    all_tables_count = 0
    
    for page_num in pages:
        print(f"📄 Processing page {page_num}...")
        
        # Construct URL for the page - adjust this based on the site's URL structure
        if "?" in base_url:
            url = f"{base_url}&page={page_num}"
        else:
            url = f"{base_url}?page={page_num}"
        
        try:
            driver.get(url)
            time.sleep(2)  # Wait for page load
            
            # Handle consent popup on each page
            handle_consent_popup(driver)
            
            # Wait for tables to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
            except TimeoutException:
                print(f"⚠️ No tables found on page {page_num}")
                continue
            
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            # Extract tables with page number in filename
            page_tables = extract_and_save_tables(
                soup, 
                f"{base_filename}_page_{page_num}",
                results_folder
            )
            all_tables_count += page_tables
            
        except Exception as e:
            print(f"❌ Error processing page {page_num}: {str(e)}")
    
    return all_tables_count


def extract_and_save_tables(soup, base_filename, folder_path="results"):
    """Extract tables from BeautifulSoup object and save as CSV files in specified folder."""
    tables = soup.find_all("table")
    
    if not tables:
        print("⚠️ No tables found on the page.")
        return 0

    saved_count = 0
    
    for i, table in enumerate(tables):
        # Try to get table ID or generate descriptive one
        table_id = table.get("id") or table.get("class", [""])[0] or f"table_{i}"
        
        # Extract table caption for better filename
        caption = table.find("caption")
        if caption:
            caption_text = re.sub(r"[^\w\s-]", "", caption.get_text().strip())
            caption_text = re.sub(r"[-\s]+", "_", caption_text)
            if caption_text:
                table_id = f"{caption_text}_{table_id}"
        
        # Extract headers
        headers = []
        header_row = table.find("thead")
        if header_row:
            # Find all th elements, skip rows with specific classes if needed
            headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
        
        # If no headers in thead, check first row of tbody
        if not headers:
            first_row = table.find("tbody").find("tr") if table.find("tbody") else table.find("tr")
            if first_row:
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(["th", "td"])]
        
        if not headers:
            print(f"⚠️ Skipping table {table_id}: No headers found")
            continue
        
        # Extract table data
        data = []
        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")
        
        for row in rows:
            # Skip header rows in tbody
            if row.find_parent("thead"):
                continue
                
            cells = row.find_all(["th", "td"])
            row_data = [cell.get_text(strip=True) for cell in cells]
            
            # Only add rows that match header length (or handle mismatches)
            if len(row_data) == len(headers) or len(row_data) > 0:
                data.append(row_data)
        
        # Create DataFrame and save
        if data:
            try:
                df = pd.DataFrame(data, columns=headers[:len(data[0])] if data else headers)
                
                # Clean filename
                safe_id = re.sub(r"[^\w\-]", "_", table_id.lower())
                safe_id = re.sub(r"_+", "_", safe_id).strip("_")
                filename = f"{base_filename}_{safe_id}.csv"
                file_path = os.path.join(folder_path, filename)
                
                # Ensure unique filename
                counter = 1
                original_file_path = file_path
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_file_path)
                    file_path = f"{name}_{counter}{ext}"
                    counter += 1
                
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                print(f"✅ Saved: {file_path} ({len(df)} rows, {len(df.columns)} columns)")
                saved_count += 1
                
            except Exception as e:
                print(f"❌ Error processing table {table_id}: {str(e)}")
        else:
            print(f"⚠️ Skipping table {table_id}: No data rows found")
    
    print(f"📊 Successfully saved {saved_count} out of {len(tables)} tables found.")
    return saved_count


def setup_driver(headless=True):
    """Set up and return Chrome WebDriver with common options."""
    options = Options()
    
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # Optional: Add user agent to avoid blocking
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def main():
    base_url = "https://fbref.com/en/comps/9/Premier-League-Stats"
    
    # Create results folder
    results_folder = ensure_results_folder()
    
    print("🌐 Launching browser...")
    driver = setup_driver(headless=True)
    
    try:
        # Option 1: Scrape single page
        print("🔗 Single page scraping mode...")
        driver.get(base_url)
        
        # Handle consent popup
        handle_consent_popup(driver)
        
        print("⏳ Waiting for page to load...")
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
        except TimeoutException:
            print("⚠️ No tables found within timeout period, but continuing...")
        
        # Additional brief wait for JavaScript content
        time.sleep(2)
        
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract and save tables to results folder
        extract_and_save_tables(soup, "premier_league_stats", results_folder)
        
        # Option 2: Uncomment to scrape multiple pages
        """
        print("🔗 Multiple pages scraping mode...")
        pages_to_scrape = [1, 2, 3]  # Adjust page numbers as needed
        total_tables = scrape_multiple_pages(
            base_url, 
            pages_to_scrape, 
            driver, 
            "premier_league_stats"
        )
        print(f"🏁 Scraping complete! Total tables saved: {total_tables}")
        """
        
        print("🏁 Scraping complete!")
        print(f"📁 All results saved in: {os.path.abspath(results_folder)}")
        
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        
    finally:
        driver.quit()
        print("🔚 Browser closed.")


if __name__ == "__main__":
    main()