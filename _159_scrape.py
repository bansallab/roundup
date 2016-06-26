import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util

default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/marketsamples.php'
strip_char = ';,. \n\t'


def get_sale_date(line):
    """Return the date of the livestock sale."""

    match = re.search(r'(.+?)receipts.*', line, re.IGNORECASE)
    if match:
        sale_date = dateutil.parser.parse(match.group(1).strip(' -'), fuzzy=True).date()
    else:
        sale_date = dateutil.parser.parse(line, fuzzy=True).date()
        
    return sale_date


def get_sale_head(line):

    match = re.search(r'receipts(.*)', line, re.IGNORECASE)
    if match:
        sale_head = match.group(1).strip()

    return sale_head


def get_sale(this_line, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    sale = {
        'consignor_city': this_line[0],
        'cattle_head': this_line[1],
        'cattle_avg_weight': this_line[2],
        }

    if len(this_line) == 5:
        cattle_cattle = this_line[4] + ' ' + cattle
        sale['cattle_price_cwt'] = this_line[3]
    else:
        split_line = this_line[3].split()
        cattle_cattle = ' '.join(split_line[1:]) + ' ' + cattle
        sale['cattle_price_cwt'] = split_line[0]

    sale['cattle_cattle'] = cattle_cattle.strip()
    sale = {k: v for k, v in sale.items() if v}

    return sale



def write_sale(row, cattle, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_row in row:
        sale = this_default_sale.copy()
        sale.update(get_sale(this_row, cattle))
        writer.writerow(sale)


def main():

    archive = scrape_util.ArchiveFolder(argv, prefix)

    request = Request(
        base_url + report_path,
        headers=scrape_util.url_header
        )

    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')

    report = [soup]

    for this_report in report:

        div = this_report.find('div', id='content')

        heading = re.compile(r'receipts', re.IGNORECASE)
        p = div.find(text=heading)
        if p:
            sale_header = p.get_text()
            sale_date = get_sale_date(sale_header)
            sale_head = get_sale_head(sale_header)
        else:
            heading = re.compile(r'\d+[,\s]+20\d{2}')
            p = div.find(text=heading)
            if p:
                sale_head = None
                sale_date = get_sale_date(p.parent.get_text())
            else:
                continue

        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        table = div.table
        row = table.find_all('tr')
        heading = [td.get_text().strip() for td in row.pop(0).find_all('td', attrs={'colspan': 4})]
        data_left = []
        data_right = []
        for this_row in row:
            this_row = [td.get_text().replace('\x97',' ').strip() for td in this_row.find_all('td')]
            if ''.join(this_row):
                data_left.append(this_row[0:5])
                data_right.append(this_row[5:])

        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(data_left, heading[0], this_default_sale, writer)
            write_sale(data_right, heading[1], this_default_sale, writer)
    

if __name__ == '__main__':
    main()
