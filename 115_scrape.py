import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util
from datetime import date


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'page05.html'
sale_pattern = re.compile(
    r'\$(?P<price>[0-9\.]+)[^0-9]+'
    r'(?P<weight>[0-9]+)[^0-9]+'
    r'(?P<head>[0-9]+)[^-]+-'
    r'(?P<name>.*?)of'
    r'(?P<location>.*)'
    )


def get_sale_date(line):

    date_string = re.sub(r'sale results', '', line, re.IGNORECASE).strip()
    sale_date = parser.parse(date_string, fuzzy=True).date()
    if sale_date == date.today():
        sale_date = None

    return sale_date


def get_sale_head(line):

    head = None
    match = re.search(r'Sold\s*([0-9]+)\sHd', line, re.IGNORECASE)
    if match:
        head = match.group(1)

    return head


def get_sale(match, cattle):

    sale_location = match.group('location').split(',')

    sale = {
        'consignor_name': match.group('name'),
        'consignor_city': sale_location.pop(0),
        'cattle_avg_weight': match.group('weight'),
        'cattle_head': match.group('head'),
        'cattle_cattle': cattle,
        'cattle_price_cwt': match.group('price'),
        }

    if sale_location:
        sale['consignor_state'] = sale_location.pop(0)

    sale = {k: v.strip() for k, v in sale.items() if v.strip()}

    return sale


def write_sale(line, default_sale, writer):

    # extract & write sale dictionary
    for this_line in filter(bool, line):
        match = sale_pattern.search(this_line)
        if not match and this_line:
            cattle = re.sub(r'\s+', ' ', this_line)
        else:
            sale = default_sale.copy()
            sale.update(get_sale(match, cattle))
            if sale != default_sale:
                writer.writerow(sale)


def main():

    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = [soup.find(id='element6')]

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:

        line = [this_line.replace('\xa0', ' ').strip() for this_line in this_report.strings]

        # sale defaults
        sale_date = get_sale_date(line.pop(0))

        # Skip if already archived
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': get_sale_head(line.pop(0))
            })

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
