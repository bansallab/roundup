import csv
import re
from urllib.request import Request, urlopen
from dateutil import parser
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'main/actual_sales.idc.htm'


def get_sale_date(tag):
    """Return the date of the livestock sale."""

    text = tag.get_text()
    sale_date = parser.parse(text).date()

    return sale_date


def is_header(line):
    is_succinct = len(line) < 2
    match = False
    if is_succinct:
        match = re.search(r':$', line[-1])
    return is_succinct and match


def is_sale(line):
    match = re.search(r'\$[\d\.]+$', line[-1])
    return bool(match)


def get_sale_location(location):

    if ',' in location:
        sale_location = location.split(',')
    elif not ' ' in location:
        sale_location = [location, '']
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [location, '']

    return sale_location


def get_sale(line, header):

    sale_location = get_sale_location(line[1])
    match = re.search(r'(?P<head>\d*)(?P<cattle>[^\d]+)(?P<weight>\d+)lbs\s\$(?P<price>[\d\.]+)', line[-1])

    sale = {
        'consignor_name': line[0].strip(','),
        'consignor_city': sale_location[0],
        'consignor_state': sale_location[1],
        'cattle_head': match.group('head'),
        'cattle_avg_weight': match.group('weight').replace(',', ''),
        'cattle_cattle': ' '.join([header, match.group('cattle').strip(', ')]),
        'cattle_price_cwt': match.group('price').replace(',', ''),
        }

    sale = {k: v.strip() for k, v in sale.items() if v.strip()}

    return sale


def write_sale(line, default_sale, writer):

    header = None
    for this_line in filter(bool, line):
        if is_header(this_line):
            header = this_line[0].strip(':')
        elif header and is_sale(this_line):
            sale = default_sale.copy()
            sale.update(get_sale(this_line, header))
            writer.writerow(sale)


def main():

    # locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # download Saturday sale page
    request = Request(
        base_url + report_path,
        headers=scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'html5lib')

    report = soup.find_all('td')

    for this_report in report:

        sale_date = get_sale_date(this_report.h3)
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

        line = [[]]
        for this_string in this_report.strings:
            if re.match(r'\r|\n(?!\d)', this_string):
                line.append([])
            this_string = re.sub(r'\r|\n|\.{2,}', ' ', this_string).strip()
            if this_string:
                match = re.match(r'([^,]+),([^,]+),(.*)', this_string)
                if match:
                    this_string = [match.group(i) for i in [1,2,3]]
                    line[-1].extend(this_string)
                elif len(line[-1]) == 4:
                    this_line = line[-1][:2]
                    this_line.append(''.join(line[-1][2:]) + this_string)
                    line[-1] = this_line
                else:
                    line[-1].append(this_string)

        # open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)

if __name__ == '__main__':
    main()
