import csv
import re
from urllib.request import Request, urlopen
from datetime import date
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'category/current-sale-report/'


def get_sale_date(date_string):
    sale_date = dateutil.parser.parse(date_string, fuzzy=True).date()
    return sale_date


def is_heading(line):
    return bool(type(line)==str)


def get_sale_location(location):

    match = re.search(r'(.*?),([^\d]*)(\d*)', location)
    sale_location = [match.group(idx) for idx in [1,2,3]]

    return sale_location


def get_sale(line, heading):

    try:
        sale_location = get_sale_location(line['Location:'])
    except KeyError:
        sale_location = get_sale_location(line['Address:'])

    sale = {
        # 'consignor_name': line['Name:'],
        'consignor_city': sale_location[0],
        'consignor_state': sale_location[1],
        'consignor_zip': sale_location[2],
        'cattle_head': line['Head:'],
        'cattle_cattle': ' '.join([heading, line['Description:']]),
        'cattle_avg_weight': re.sub('[^\d\.]', '', line['Avg WT:']),
        'cattle_price_cwt': re.sub('[^\d\.]', '', line['Bid:']),
        }

    sale = {k: v.strip() for k, v in sale.items() if v.strip()}

    return sale



def write_sale(line, default_sale, writer):

    heading = None
    for this_line in line:
        if is_heading(this_line):
            heading = this_line
        else:
            sale = default_sale.copy()
            sale.update(get_sale(this_line, heading))
            writer.writerow(sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    report = soup.find_all('article', attrs={'class': 'post'})

    for this_report in report:

        title = this_report.find('h2', attrs={'class': 'post-title'})
        if 'horse' in title.get_text().lower():
            continue

        date_string = this_report.find(text=re.compile('Market Report'))
        sale_date = get_sale_date(date_string)
        io_name = archive.new_csv(sale_date)

        #Stop iteration if this report is already archived
        if not io_name:
            continue

        table = this_report.find_all('table')
        line = []
        for this_table in table:
            line.append(this_table.caption.get_text())
            line.extend([
                {td['data-label'].strip(): td.get_text() for td in tr.find_all('td')}
                for tr in this_table.find_all('tr') if tr.td
                ])

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
