import csv
import re
import dateutil.parser
import scrape_util
from urllib.request import Request, urlopen
from sys import argv
from bs4 import BeautifulSoup


default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t'


def get_sale_date(date_head):
    """Return the date of the livestock sale."""
    date_string = date_head[0]
    report_date = date_string.split(",")
    reportmd = report_date[0].split()[-2:]
    reportmd.append(report_date[-1])
    date_string = str(reportmd)
    sale_date = dateutil.parser.parse(date_string, fuzzy = True)
    return sale_date


def get_sale_head(date_head):
    """Return the date of the livestock sale."""

    head_string = date_head[-1].replace("\n","").strip()
    return head_string


def is_sale(line):

    line = [this_col for this_col in line if this_col]
    has_price = re.search(r'\$[0-9]+', line[-1])

    return bool(has_price) and len(line)==4


def get_sale_location(location):

    if ',' in location:
        sale_location = location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [location, '']

    return sale_location


def get_sale(line):

    sale_location = get_sale_location(line[0])

    sale = {
        'consignor_city': sale_location[0].title(),
        'consignor_state': sale_location[1],
        'cattle_avg_weight': re.sub(r'[^0-9\.]', '', line[2]),
        'cattle_price_cwt': re.sub(r'[^0-9\.]', '', line[3]),
    }

    match = re.match(r'([0-9]+)\s(.*)', line[1])
    if match:
        sale['cattle_head'] = match.group(1)
        sale['cattle_cattle'] = match.group(2)

    sale = {k: v for k, v in sale.items() if v}

    return sale


def write_sale(line, default_sale, writer):

    for this_line in line:
        if is_sale(this_line):
            sale = default_sale.copy()
            sale.update(get_sale(this_line))
            writer.writerow(sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    report = ['/repsales.php']

    for this_report in report:

        # Download auxillary information
        request = Request(
            base_url + '/comm.php',
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read(), 'lxml')

        table = soup.find_all("table")
        commentary = table[1].tr.td.get_text()
        date_and_head = commentary.split(":")
        sale_date = get_sale_date(date_and_head)
        io_name = archive.new_csv(sale_date)

        #Stop iteration if this report is already archived
        if not io_name:
            break

        # Initialize the default sale dictionary
        sale_head = get_sale_head(date_and_head)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                'sale_head': sale_head,
                })

        # Download report
        request = Request(
            base_url + this_report,
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read(), 'lxml')
        table = soup.find_all('table')
        line = [[td.get_text() for td in tr.find_all('td')] for tr in table[1].find_all('tr')]

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)

if __name__ == '__main__':
    main()
