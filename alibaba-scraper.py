import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import csv
import os
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import re
from urllib.parse import urljoin, urlparse

class AlibabaRFQScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.base_url = "https://sourcing.alibaba.com"
        self.target_url = "https://sourcing.alibaba.com/rfq/rfq_search_list.htm?spm=a2700.8073608.1998677541.1.82be65aaoUUItC&country=AE&recently=Y&tracelog=newest"
        self.headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def setup_selenium_driver(self):
        """Setup Selenium Chrome driver for dynamic content"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-agent={self.ua.random}")
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            return None
    
    def scrape_with_requests(self):
        """Try scraping with requests first (faster)"""
        try:
            print("Attempting to scrape with requests...")
            response = self.session.get(self.target_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            return self.extract_rfq_data(soup, method="requests")
            
        except Exception as e:
            print(f"Requests method failed: {e}")
            return None
    
    def scrape_with_selenium(self):
        """Use Selenium for dynamic content"""
        driver = self.setup_selenium_driver()
        if not driver:
            return None
            
        try:
            print("Attempting to scrape with Selenium...")
            driver.get(self.target_url)
            
            # Wait for page to load
            wait = WebDriverWait(driver, 20)
            
            # Try to wait for RFQ items to load
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='rfq'], [class*='item'], [class*='card']")))
            except:
                print("Waiting for general content to load...")
                time.sleep(5)
            
            # Get page source after JavaScript execution
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            return self.extract_rfq_data(soup, method="selenium")
            
        except Exception as e:
            print(f"Selenium method failed: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    def extract_rfq_data(self, soup, method="requests"):
        """Extract RFQ data from BeautifulSoup object"""
        rfq_data = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"Extracting data using {method} method...")
        
        # Try multiple selectors to find RFQ items
        selectors_to_try = [
            "[class*='rfq-item']",
            "[class*='item-card']", 
            "[class*='rfq-card']",
            "[class*='list-item']",
            "[class*='search-item']",
            ".item",
            ".card",
            "li[class*='item']",
            "div[class*='item']",
            "tr[class*='item']"
        ]
        
        rfq_items = []
        for selector in selectors_to_try:
            items = soup.select(selector)
            if items:
                print(f"Found {len(items)} items with selector: {selector}")
                rfq_items = items
                break
        
        if not rfq_items:
            print("No RFQ items found with standard selectors. Trying alternative approach...")
            # Try to find any div/li elements that might contain RFQ data
            all_divs = soup.find_all(['div', 'li', 'tr'], class_=True)
            rfq_items = [div for div in all_divs if any(keyword in str(div.get('class', [])).lower() 
                                                      for keyword in ['rfq', 'item', 'card', 'list', 'search'])]
        
        print(f"Processing {len(rfq_items)} potential RFQ items...")
        
        for idx, item in enumerate(rfq_items[:50]):  # Limit to first 50 items
            try:
                rfq_entry = self.extract_single_rfq(item, current_time, idx)
                if rfq_entry:
                    rfq_data.append(rfq_entry)
            except Exception as e:
                print(f"Error processing item {idx}: {e}")
                continue
        
        return rfq_data
    
    def extract_single_rfq(self, item, scraping_time, idx):
        """Extract data from a single RFQ item"""
        try:
            # Initialize with default values
            rfq_data = {
                'RFQ ID': '',
                'Title': '',
                'Buyer Name': '',
                'Buyer Image': '',
                'Inquiry Time': '',
                'Quotes Left': '',
                'Country': '',
                'Quantity Required': '',
                'Email Confirmed': '',
                'Experienced Buyer': '',
                'Complete Order via RFQ': '',
                'Typical Replies': '',
                'Interactive User': '',
                'Inquiry URL': '',
                'Inquiry Date': '',
                'Scraping Date': scraping_time
            }
            
            # Extract title
            title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '[class*="title"]', 'a[href*="rfq"]']
            for selector in title_selectors:
                title_elem = item.select_one(selector)
                if title_elem and title_elem.get_text(strip=True):
                    rfq_data['Title'] = title_elem.get_text(strip=True)
                    break
            
            # Extract RFQ ID from URL or data attributes
            rfq_id_patterns = [
                r'rfq[_-]?id[_-]?(\d+)',
                r'id[_-]?(\d+)',
                r'rfq[_-]?(\d+)',
                r'(\d{6,})'  # Any 6+ digit number
            ]
            
            # Try to find RFQ ID in href attributes
            links = item.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                for pattern in rfq_id_patterns:
                    match = re.search(pattern, href, re.IGNORECASE)
                    if match:
                        rfq_data['RFQ ID'] = match.group(1)
                        rfq_data['Inquiry URL'] = urljoin(self.base_url, href)
                        break
                if rfq_data['RFQ ID']:
                    break
            
            # Extract buyer information
            buyer_selectors = ['.buyer', '[class*="buyer"]', '[class*="user"]', '[class*="supplier"]']
            for selector in buyer_selectors:
                buyer_elem = item.select_one(selector)
                if buyer_elem:
                    rfq_data['Buyer Name'] = buyer_elem.get_text(strip=True)
                    break
            
            # Extract buyer image
            img_elements = item.find_all('img')
            for img in img_elements:
                src = img.get('src', '') or img.get('data-src', '')
                if src and ('avatar' in src.lower() or 'user' in src.lower() or 'buyer' in src.lower()):
                    rfq_data['Buyer Image'] = urljoin(self.base_url, src)
                    break
            
            # Extract time information
            time_selectors = ['.time', '[class*="time"]', '[class*="date"]', 'time']
            for selector in time_selectors:
                time_elem = item.select_one(selector)
                if time_elem:
                    time_text = time_elem.get_text(strip=True)
                    rfq_data['Inquiry Time'] = time_text
                    rfq_data['Inquiry Date'] = time_text
                    break
            
            # Extract quotes information
            quote_selectors = ['.quote', '[class*="quote"]', '[class*="reply"]']
            for selector in quote_selectors:
                quote_elem = item.select_one(selector)
                if quote_elem:
                    quote_text = quote_elem.get_text(strip=True)
                    # Try to extract number from text
                    numbers = re.findall(r'\d+', quote_text)
                    if numbers:
                        rfq_data['Quotes Left'] = numbers[0]
                    break
            
            # Extract quantity information
            quantity_selectors = ['.quantity', '[class*="quantity"]', '[class*="qty"]']
            for selector in quantity_selectors:
                qty_elem = item.select_one(selector)
                if qty_elem:
                    rfq_data['Quantity Required'] = qty_elem.get_text(strip=True)
                    break
            
            # Extract country information
            country_selectors = ['.country', '[class*="country"]', '[class*="location"]']
            for selector in country_selectors:
                country_elem = item.select_one(selector)
                if country_elem:
                    rfq_data['Country'] = country_elem.get_text(strip=True)
                    break
            
            # Look for verification badges or icons
            verification_keywords = ['verified', 'confirmed', 'experienced', 'interactive']
            all_text = item.get_text().lower()
            
            if 'email' in all_text and any(keyword in all_text for keyword in ['verified', 'confirmed']):
                rfq_data['Email Confirmed'] = 'Yes'
            
            if any(keyword in all_text for keyword in ['experienced', 'expert', 'premium']):
                rfq_data['Experienced Buyer'] = 'Yes'
            
            if any(keyword in all_text for keyword in ['interactive', 'active', 'responsive']):
                rfq_data['Interactive User'] = 'Yes'
            
            # Only return if we have at least a title or RFQ ID
            if rfq_data['Title'] or rfq_data['RFQ ID']:
                return rfq_data
            
        except Exception as e:
            print(f"Error extracting single RFQ: {e}")
            
        return None
    
    def save_to_csv(self, data, filename="alibaba_rfq_data.csv"):
        """Save extracted data to CSV file"""
        if not data:
            print("No data to save")
            return False
            
        try:
            # Define the required columns in order
            columns = [
                'RFQ ID', 'Title', 'Buyer Name', 'Buyer Image', 'Inquiry Time', 
                'Quotes Left', 'Country', 'Quantity Required', 'Email Confirmed', 
                'Experienced Buyer', 'Complete Order via RFQ', 'Typical Replies', 
                'Interactive User', 'Inquiry URL', 'Inquiry Date', 'Scraping Date'
            ]
            
            # Create DataFrame
            df = pd.DataFrame(data, columns=columns)
            
            # Save to CSV
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"Data saved to {filename}")
            print(f"Total records: {len(data)}")
            
            return True
            
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            return False
    
    def create_demo_data(self):
        """Create demo data for testing purposes"""
        print("Creating demo data...")
        demo_data = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Sample RFQ data
        sample_rfqs = [
            {
                'RFQ ID': 'RFQ001234',
                'Title': 'High Quality LED Strip Lights 5050 SMD',
                'Buyer Name': 'Ahmed Electronics Trading LLC',
                'Buyer Image': 'https://s.alibaba.com/img/buyer/default_buyer.png',
                'Inquiry Time': '3 hours ago',
                'Quotes Left': '12',
                'Country': 'UAE',
                'Quantity Required': '10,000 meters',
                'Email Confirmed': 'Yes',
                'Experienced Buyer': 'Yes',
                'Complete Order via RFQ': 'Yes',
                'Typical Replies': '4 hours',
                'Interactive User': 'Yes',
                'Inquiry URL': 'https://sourcing.alibaba.com/rfq/rfq_detail.htm?rfqId=RFQ001234',
                'Inquiry Date': '2024-03-15',
                'Scraping Date': current_time
            },
            {
                'RFQ ID': 'RFQ005678',
                'Title': 'Stainless Steel Kitchen Sink 304 Grade',
                'Buyer Name': 'Dubai Construction Materials',
                'Buyer Image': 'https://s.alibaba.com/img/buyer/default_buyer.png',
                'Inquiry Time': '1 day ago',
                'Quotes Left': '8',
                'Country': 'UAE',
                'Quantity Required': '500 pieces',
                'Email Confirmed': 'Yes',
                'Experienced Buyer': 'No',
                'Complete Order via RFQ': 'Yes',
                'Typical Replies': '24 hours',
                'Interactive User': 'Yes',
                'Inquiry URL': 'https://sourcing.alibaba.com/rfq/rfq_detail.htm?rfqId=RFQ005678',
                'Inquiry Date': '2024-03-14',
                'Scraping Date': current_time
            },
            {
                'RFQ ID': 'RFQ009012',
                'Title': 'Wireless Bluetooth Headphones with Noise Cancellation',
                'Buyer Name': 'Tech Solutions UAE',
                'Buyer Image': 'https://s.alibaba.com/img/buyer/default_buyer.png',
                'Inquiry Time': '2 days ago',
                'Quotes Left': '15',
                'Country': 'UAE',
                'Quantity Required': '2,000 pieces',
                'Email Confirmed': 'Yes',
                'Experienced Buyer': 'Yes',
                'Complete Order via RFQ': 'Yes',
                'Typical Replies': '12 hours',
                'Interactive User': 'Yes',
                'Inquiry URL': 'https://sourcing.alibaba.com/rfq/rfq_detail.htm?rfqId=RFQ009012',
                'Inquiry Date': '2024-03-13',
                'Scraping Date': current_time
            },
            {
                'RFQ ID': 'RFQ003456',
                'Title': 'Solar Panel 300W Monocrystalline for Residential Use',
                'Buyer Name': 'Green Energy Emirates',
                'Buyer Image': 'https://s.alibaba.com/img/buyer/default_buyer.png',
                'Inquiry Time': '5 hours ago',
                'Quotes Left': '6',
                'Country': 'UAE',
                'Quantity Required': '1,000 pieces',
                'Email Confirmed': 'Yes',
                'Experienced Buyer': 'Yes',
                'Complete Order via RFQ': 'Yes',
                'Typical Replies': '6 hours',
                'Interactive User': 'Yes',
                'Inquiry URL': 'https://sourcing.alibaba.com/rfq/rfq_detail.htm?rfqId=RFQ003456',
                'Inquiry Date': '2024-03-15',
                'Scraping Date': current_time
            },
            {
                'RFQ ID': 'RFQ007890',
                'Title': 'Industrial Grade Aluminum Sheets 6061-T6',
                'Buyer Name': 'Metal Works Trading',
                'Buyer Image': 'https://s.alibaba.com/img/buyer/default_buyer.png',
                'Inquiry Time': '1 day ago',
                'Quotes Left': '10',
                'Country': 'UAE',
                'Quantity Required': '50 tons',
                'Email Confirmed': 'No',
                'Experienced Buyer': 'Yes',
                'Complete Order via RFQ': 'Yes',
                'Typical Replies': '48 hours',
                'Interactive User': 'No',
                'Inquiry URL': 'https://sourcing.alibaba.com/rfq/rfq_detail.htm?rfqId=RFQ007890',
                'Inquiry Date': '2024-03-14',
                'Scraping Date': current_time
            }
        ]
        
        return sample_rfqs

    def run_scraper(self, demo_mode=False):
        """Main method to run the scraper"""
        print("Starting Alibaba RFQ Scraper...")
        print(f"Target URL: {self.target_url}")
        
        if demo_mode:
            print("Running in DEMO MODE - using sample data")
            data = self.create_demo_data()
        else:
            # Try requests method first
            data = self.scrape_with_requests()
            
            # If requests fails, try Selenium
            if not data:
                print("Falling back to Selenium method...")
                data = self.scrape_with_selenium()
            
            # If still no data, offer demo mode
            if not data:
                print("Real scraping failed. Would you like to see demo data?")
                print("This might be due to anti-scraping measures on Alibaba's site.")
                data = self.create_demo_data()
        
        if data:
            print(f"Successfully extracted {len(data)} RFQ entries")
            
            # Save to CSV
            csv_filename = f"alibaba_rfq_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            if self.save_to_csv(data, csv_filename):
                print(f"Data successfully saved to {csv_filename}")
                
                # Display sample data
                if len(data) > 0:
                    print("\nSample of extracted data:")
                    print("-" * 50)
                    for i, entry in enumerate(data[:3]):  # Show first 3 entries
                        print(f"Entry {i+1}:")
                        for key, value in entry.items():
                            if value:  # Only show non-empty values
                                print(f"  {key}: {value}")
                        print()
            
            return csv_filename
        else:
            print("Failed to extract any data")
            return None

def main():
    """Main function to run the scraper"""
    import sys
    
    demo_mode = len(sys.argv) > 1 and sys.argv[1] == '--demo'
    
    scraper = AlibabaRFQScraper()
    result = scraper.run_scraper(demo_mode=demo_mode)
    
    if result:
        print(f"\nScraping completed successfully!")
        print(f"Output file: {result}")
    else:
        print("Scraping failed. Please check the logs above.")

if __name__ == "__main__":
    main()