import csv
import requests
import re
import scrape_util
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup
from datetime import date, timedelta
from os import system
from pathlib import Path


## info from market owner:
# "we do post the market report on Tues for the Monday sale and then"
# "combine them at the end of the week"


default_sale, base_url, prefix = scrape_util.get_market(argv)
temp_raw = scrape_util.ReportRaw(argv, prefix)
date_pattern = re.compile(r'PDFs/MarketReports/(?P<year>\d+)/\w+/(?P<month>\d+)-(?P<day>\d+).*\.pdf')
head_pattern = re.compile(r'(?P<location>.*)(\u2013|-)[^\d\.]+(?P<receipts>[\d,]*)')
rep_pattern = re.compile(r'rep(resentative)?\s+sales?:', re.IGNORECASE)
sale_pattern = [
    re.compile(
        r'(?P<name>.*?),(?!\s*(I+|Jr|LLC|LP|Inc|Ltd|MB|DVM))\s*'
        r'(?P<city>[^,\d]+),\s*'
        r'(?P<head>\d+)\s+'
        r'(?P<cattle>[^\d]+)'
        r'(?P<weight>\d*)\s[^\d]*'
        r'(?P<price>[\d\.]+)'
        ),
    re.compile(
        r'(?P<name>.*?),(?!\s*(I+|Jr|LLC|LP|Inc|Ltd|MB|DVM))\s*'
        r'(?P<city>[^\d]+)(?=\d+\s+heifers)'
        r'(?P<head>\d+)\s+'
        r'(?P<cattle>[^\d]+)'
        r'(?P<weight>\d*)\s[^\d]*'
        r'(?P<price>[\d\.]+)'
        ),
    re.compile(
        r'(?P<name>.*?),(?!\s*(I+|Jr|LLC|LP|Inc|Ltd|MB|DVM))\s*'
        r'(?P<head>\d+)'
        r'(?P<cattle>.*?)'
        r'(?P<price>(\d+\.\d+|\$\d+))'
        ),
    ]


def get_sale_date(href):

    match = date_pattern.match(href)
    if match:
        sale_date = [int(match.group(k)) for k in ['year', 'month', 'day']]
        sale_date = date(*sale_date)
    else:
        sale_date = None

    return sale_date


def get_sale_location_and_receipts(line):

    match = head = location = None
    while not match:
        try:
            this_line = line.pop(0)
        except IndexError:
            break
        match = head_pattern.match(this_line)
    if match:
        location = match.group('location').lower()
        receipts = match.group('receipts').replace(',','')

    return location, receipts


def get_sale(line):

    for i, p in enumerate(sale_pattern):
        match = p.match(line)
        if match:
            break
    if not match:
        print('No match in {}: {}'.format(argv[0], line))
        return {}
    sale = {
        'consignor_name': match.group('name').strip(','),
        'cattle_head': match.group('head'),
        'cattle_cattle': match.group('cattle').replace(',', ''),
        }
    if i < 2:
        sale.update({
            'consignor_city': match.group('city'),
            'cattle_avg_weight': match.group('weight'),
            'cattle_price_cwt': match.group('price'),
            })
    elif i == 2:
        sale.update({
            'cattle_price': match.group('price').replace('$', ''),
            })

    sale = {k: v.strip() for k, v in sale.items() if v.strip()}
    return sale


def write_sale(line, exist_sale, this_default_sale, writer):

    is_sale = False
    exist_sale = set(exist_sale.items()) if exist_sale else set()
    for this_line in line:
        if rep_pattern.match(this_line):
            is_sale = True
            continue
        if not is_sale:
            continue
        sale = get_sale(this_line)
        if sale:
            if exist_sale >= set(sale.items()): break
            this_sale = this_default_sale.copy()
            this_sale.update(sale)
            writer.writerow(this_sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Collect list of market reports
    session = requests.Session()
    session.headers.update(scrape_util.url_header)
    response = session.get(url=(base_url + '/market-reports.html'))
    soup = BeautifulSoup(response.content)
    report = [a for a in soup.find_all('a') if a.get('href', '').startswith('PDFs/MarketReports')]

    # Process each market report
    for this_report in report:

        # Stop iteration if this report is already archived
        sale_date = get_sale_date(this_report['href'])
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        # Request the report PDF and convert to TXT
        response = session.get(url=(base_url + this_report['href']))
        with temp_raw.open('wb') as io:
            io.write(response.content)
        system(scrape_util.pdftotext.format(str(temp_raw)))
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = [this_line for this_line in io if this_line.strip()]
        temp_raw.clean()

        # Attribute sale to a location, if unique
        sale_location, sale_head = get_sale_location_and_receipts(line)
        exist_sale = None
        if (
            default_sale[0]['sale_city'].lower() in sale_location
            and default_sale[1]['sale_city'].lower() in sale_location
            ):
            exist_date = (sale_date - timedelta(days=3)).strftime('%y-%m-%d')
            exist_report = io_name.parent / Path('{}_{}.csv'.format(prefix, exist_date))
            if not exist_report.exists():
                exist_report = io_name.parent / Path('dbased/{}_{}.csv'.format(prefix, exist_date))
            if not exist_report.exists():
                with io_name.open('w', encoding='utf-8') as io:
                    writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                    writer.writeheader()
                continue
            with exist_report.open('r') as io:
                this_default_sale = default_sale[1].copy()
                reader = csv.DictReader(io)
                exist_sale = next(reader)
                sale_head = int(sale_head) - int(exist_sale['sale_head'])
        elif default_sale[0]['sale_city'].lower() in sale_location:
            this_default_sale = default_sale[0].copy()
        elif default_sale[1]['sale_city'].lower() in sale_location:
            this_default_sale = default_sale[1].copy()
        else:
            raise Exception

        # Initialize the default sale dictionary
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
            write_sale(line, exist_sale, this_default_sale, writer)


if __name__ == '__main__':
    main()
