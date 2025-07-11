Alibaba RFQ Scraper (Python)
This is a Python-based scraper that collects RFQ (Request for Quotation) listings from Alibaba. It uses a hybrid approach of Requests and Selenium to ensure both static and JavaScript-rendered content is captured effectively.

Features
Extracts RFQ data: titles, buyer name, country, inquiry time, quotes left, etc.

Uses BeautifulSoup for static content and Selenium for dynamic content

Saves data into CSV format

Includes demo mode with sample data

Handles user-agent spoofing and basic anti-scraping defenses

Technologies Used
Python

requests

BeautifulSoup4

selenium

pandas

fake-useragent

webdriver-manager

Installation
bash
Copy
Edit
git clone https://github.com/yourusername/alibaba-rfq-scraper-python.git
cd alibaba-rfq-scraper-python
pip install -r requirements.txt
Usage
To run the scraper with live data:

nginx
Copy
Edit
python scraper.py
To run in demo mode (loads sample data):

css
Copy
Edit
python scraper.py --demo
Output
Data is saved as alibaba_rfq_data_<timestamp>.csv

Sample output preview is printed to console

Example Data Fields
RFQ ID

Title

Buyer Name

Buyer Image

Country

Inquiry Date and Time

Quantity Required

Quotes Left

License
This project is for educational and research purposes. Scrape responsibly and follow Alibaba’s terms of service.
