import csv
import re
from urllib.request import Request, urlopen
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import date
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/BLA/print'


def get_sale_date(soup):

    date_string = soup.find('h2').string
    sale_date = parser.parse(date_string).date()
    if sale_date > date.today():
        sale_date = None

    return sale_date


def get_sale_head(soup):

    head_pattern = re.compile('(\d+)\s+head', re.IGNORECASE)
    string = soup.body.stripped_strings
    match = None
    while not match:
        match = head_pattern.match(next(string))

    return match.group(1)


def get_sale(tr):

    text = [td.string for td in tr.find_all('td')]
    text = [s if s else '' for s in text]
    try:
        int(text[1])
    except ValueError:
        sale = {
            'consignor_city': ' '.join(text[0:2]),
            'cattle_head': text[2],
            'cattle_cattle': text[3],
            }
    else:
        sale = {
            'consignor_city': text[0],
            'cattle_head': text[1],
            'cattle_cattle': text[2],
            'cattle_avg_weight': text[3].replace(',', ''),
            }
    sale['cattle_price_cwt'] = text[4].strip('$').replace(',', '')
    sale = {k: v.strip() for k, v in sale.items() if v.strip()}

    return sale


def write_sale(table, default_sale, writer):

    # extract & write sale dictionary
    for tr in table.find_all('tr'):
        try:
            colspan = tr.td['colspan']
        except KeyError:
            sale = default_sale.copy()
            sale.update(get_sale(tr))
            if sale != default_sale:
                writer.writerow(sale)
        except TypeError:
            pass


def main():

    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = [soup]

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:

        # sale defaults
        sale_date = get_sale_date(this_report)

        # Skip if already archived
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': get_sale_head(this_report)
            })

        # open csv file and write header
        table = this_report.find('table')
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(table, this_default_sale, writer)


if __name__ == '__main__':
    main()
