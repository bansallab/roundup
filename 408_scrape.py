import re
import requests
import scrape_util
import csv
from sys import argv
from os import system
from dateutil import parser
from bs4 import BeautifulSoup
from datetime import date, timedelta
from pathlib import Path


default_sale, base_url, prefix = scrape_util.get_market(argv)
base_url = base_url.replace('http', 'https')
params = {'access_token': '|'.join(['1774881112740993', 'fca3df22db43197e4768b8448a31c365'])}
head_pattern = re.compile(r'headcount:?\s*(?P<head>\d+)', re.IGNORECASE)
cattle_pattern = [
    re.compile(r'~?(?P<cattle>(holstein|beef)?\s*steers)', re.IGNORECASE),
    re.compile(r'~?(?P<cattle>(spade|beef)?\s*heifers)', re.IGNORECASE),
    re.compile(r'~?(?P<cattle>bulls)', re.IGNORECASE),
    re.compile(r'~?(?P<cattle>cows)', re.IGNORECASE),
    ]
sale_pattern = [
    re.compile(
        r'(?P<head>\d+)(hd)?\s*,'
        r'(?P<cattle>[^,]+),'
        r'(?P<city>.*?),\s*(?=\d)'
        r'(?P<weight>[\d,]+)\s*(lb|bl)[^\$]*'
        r'\$\s*(?P<price>[\d\.]+)'
        ),
    re.compile(
        r'(?P<head>\d+)hd\s*,?'
        r'(?P<cattle>[^,]+),'
        r'(?P<city>[^\d\s]+)'
        r'(?P<weight>\d+)\s*lb[^\$]*'
        r'\$\s*(?P<price>[\d\.]+)'
        ),
    re.compile(
        r'(?P<head>\d+)(hd)?\s*,'
        r'(?P<cattle>)'
        r'(?P<city>.*?),\s*(?=\d)'
        r'(?P<weight>[\d,]+)\s*(lb|bl)[^\$]*'
        r'\$\s*(?P<price>[\d\.]+)'
        ),
    re.compile(
        r'(?P<head>\d+)hd\s*,?'
        r'(?P<cattle>[^,]+),'
        r'(?P<city>[^\d]+)'
        r'(?P<weight>\d+)\s*lb[^\d]*'
        r'(?P<price>[\d\.]+)'
        )
    ]


def get_sale_date(line, year):

    date_string = line.replace('~~MARKET REPORT~~', '').strip()
    if year not in line:
        date_string += ' ' + year
    sale_date = parser.parse(date_string).date()
    if sale_date >= date.today():
        sale_date = None

    return sale_date


def get_sale_head(line):

    match = head_pattern.search(line)
    if match:
        sale_head = match.group('head')
    else:
        sale_head = ''
    return sale_head


def get_sale(cattle, match):

    location = match.group('city')
    location_match = re.search(r'([^,]*?),?\s*(' + scrape_util.state + ')', location)
    if location_match:
        sale_location = [location_match.group(1), location_match.group(2)]
    else:
        sale_location = [location, '']

    sale = {
        'consignor_city': sale_location[0].strip(',.'),
        'consignor_state': sale_location[1].strip(',.'),
        'cattle_head': match.group('head'),
        'cattle_cattle': ' '.join([cattle, match.group('cattle').strip()]),
        'cattle_avg_weight': match.group('weight').replace(',', ''),
        'cattle_price_cwt': match.group('price').replace(',', ''),
        }
    
    sale = {k: v.strip() for k, v in sale.items() if v.strip()}
    return sale


def get_end_of_report(line):

    end_of_report = True
    while True:
        if 'choice stocker' in line: break
        if line.startswith('Pairs'): break
        if 'grass to lease' in line: break
        if 'Events' in line: break
        end_of_report = False
        break

    return end_of_report



def write_sale(line, this_default_sale, writer):

    cattle = ''
    end_of_report = False
    for this_line in line:
        for pattern in cattle_pattern:
            match = pattern.match(this_line)
            if match: break
        if match:
            cattle = match.group('cattle').strip()
            continue                
        if not cattle:
            continue
        for pattern in sale_pattern:
            match = pattern.search(this_line)
            if match: break
        if not match:
            end_of_report = get_end_of_report(this_line)
        if end_of_report:
            break
        sale = get_sale(cattle, match)
        if sale:
            this_sale = this_default_sale.copy()
            this_sale.update(sale)
            writer.writerow(this_sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Collect list of market reports
    session = requests.Session()
    session.headers.update(scrape_util.url_header)
    response = session.get(url=base_url, params=params)

    paging = True
    while paging:

        feed = response.json()
        report = (
            data for data in feed['data']
            if 'message' in data
            )

        # Process each market report
        for this_report in report:

            msg = this_report['message']
            if not msg.startswith('~~MARKET REPORT~~'):
                continue

            line = [line.strip() for line in msg.splitlines() if line.strip()]

            # Stop iteration if this report is already archived
            year = this_report['created_time'][:4]
            sale_date = get_sale_date(line.pop(0), year)
            io_name = archive.new_csv(sale_date)
            if not io_name:
                continue

            # Initialize the default sale dictionary
            sale_head = get_sale_head(line.pop(0))
            this_default_sale = default_sale.copy()
            this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                'sale_head': sale_head,
                })

            # Open a new CSV file and write each sale
            with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()
                write_sale(line, this_default_sale, writer)

        # Continue to next page
        if io_name and 'paging' in feed and 'next' in feed['paging']:
            response = session.get(url=feed['paging']['next'])
        else:
            paging = False


if __name__ == '__main__':
    main()
