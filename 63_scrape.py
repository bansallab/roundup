import csv
import xlrd
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
import scrape_util
from bs4 import BeautifulSoup
from os import system

#url_stub = 'https://www.dropbox.com/sh/nz81bwpg2wuj5q7/AACxr0xlvESoJpXLqWcOfLv_a/Market%20Report.xlsx?raw=1'
#temp_raw = scrape_util.ReportRaw(argv, prefix, suffix='xlsx')
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/market-reports.html'
temp_raw = scrape_util.ReportRaw(argv, prefix)
sale_pattern = [
    re.compile(
        r'(?P<head>[0-9]*)\s+'
        r'(?P<cattle>[^0-9]+)'
        r'(?P<weight>[0-9]+)\s+'
        r'\$(?P<price>[0-9,\.]+)\s+'
        r'(?P<location>.+)'
        ),
    re.compile(
        r'(?P<head>[0-9]*)\s+'
        r'(?P<cattle>[^\$]+)'
        r'\$(?P<price>[0-9,\.]+)\s+'
        r'(?P<location>.+)'
        )
    ]


def get_sale_date(line):

    clue = 'CATTLE RESULTS FROM:'
    match = False
    while not match:
        search_string = line.pop(0)
        match = clue in search_string
    sale_date = dateutil.parser.parse(search_string.replace(clue, '')).date()

    return sale_date


def is_sale(line):

    has_price = re.search(r'\$[0-9]+\.[0-9]{2}', line)
    is_long = len(line.split('  ')) >= 4

    return is_long and bool(has_price)


def is_heading(line):
    """Determine whether a given line is a section header
    that describes subsequent lines of a report.
    """

    has_cattle = re.search(r'steer?|hfrs?|calves|cows?|bulls?', line, re.IGNORECASE)
    has_price = re.search(r'\$[0-9]+\.[0-9]{2}', line)

    return bool(has_cattle) and not bool(has_price)


def get_sale_location(sale_location):
    """Convert address strings into a list of address components."""

    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def get_sale(line, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    match = False
    if not match:
        match = sale_pattern[0].search(line)
        price_type = 'cattle_price_cwt'
    if not match:
        match = sale_pattern[1].search(line)
        price_type = 'cattle_price'
    if not match:
        return {}

    sale_location = get_sale_location(match.group('location'))

    sale = {
        'consignor_city': sale_location.pop(0).title(),
        'cattle_head': match.group('head'),
        'cattle_cattle': ' '.join([cattle, match.group('cattle')]),
        price_type: match.group('price').replace(',', ''),
        }
    try:
        sale['cattle_avg_weight'] = match.group('weight')
    except IndexError:
        pass

    if sale_location:
        sale['consignor_state'] = sale_location.pop()

    sale = {k: v.strip() for k, v in sale.items() if v.strip()}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    for this_line in line:
        if 'HOGS' in this_line:
            break
        elif is_heading(this_line):
            cattle = this_line.strip()
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line, cattle))
            writer.writerow(sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    tag = soup.find(text='Download File')
    report = [tag.parent]

    # Write a CSV file for each report not in the archive
    for this_report in report:

        request = Request(
            base_url + this_report['href'],
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = [this_line.strip() for this_line in io if this_line.strip()]
        temp_raw.clean()

        sale_date = get_sale_date(line)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
