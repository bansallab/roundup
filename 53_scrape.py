import csv
from datetime import date
import re
from urllib.request import Request, urlopen
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market.htm'
dash = b'\xe2\x80\x94'.decode()


def report_generator(table):
    while table:
        yield table
        table = table.find_next('table')


def get_sale_date(tr):
    """Return the date of the livestock sale."""

    text = tr.span.get_text()
    sale_date = dateutil.parser.parse(text).date()
    if sale_date > date.today():
        sale_date = sale_date.replace(year=(sale_date.year - 1))
    if sale_date==date.today():
        sale_date = None

    return sale_date


def is_header(line):
    has_cattle = re.search(r'HEIFER|COW|STEER|BULL', line)
    return bool(has_cattle)


def is_cattle(header):
    return bool(re.search(r'heifer|bull|steer|pair', header, re.IGNORECASE))


def is_sale(text):
    has_symbol = '$' in text or '@' in text
    return has_symbol


def is_number(word):
    match = re.match(r'\$?[0-9,\.]+#?$', word)
    return match


def get_sale_location(location):
    sale_location = [location, '']
    if ',' in location:
        location = location.split(',')
        match = re.search(scrape_util.state, location[1])
        if match:
            sale_location = [location[0], match.group(0)]
    return sale_location


def get_sale(line, header):

    price_type = 'cattle_price'
    weight = ''
    if '@' in line:
        match = re.search(r'(.*?)([0-9]+)(.*?)([0-9\s\-]+)@(.*)', line)
        cattle = match.group(3)
        weight = match.group(4)
        try:
            weight_n = int(weight)
        except:
            weight_n = 0
        if '-' in weight or weight_n < 100:
            cattle += weight
            weight = ''
        price = match.group(5)
        if line[-1]!='H':
            price_type += '_cwt'
    elif '$' in line:
        match = re.search(r'(.*?)([0-9]+)(.*?)\$(.*)', line)
        cattle = match.group(3)
        price = match.group(4)

    sale_location = get_sale_location(match.group(1))
    sale = {
        'consignor_city': sale_location.pop(0),
        'cattle_head': match.group(2),
        'cattle_cattle': header + ' ' + cattle.strip(),
        'cattle_avg_weight': weight,
        price_type: re.sub(r'[^0-9\.]', '', price),
        }
    if sale_location:
        sale['consignor_state'] = sale_location.pop()

    sale = {k: v.strip() for k, v in sale.items() if v}

    return sale


def write_sale(line, default_sale, writer):

    for this_line in line:
        if is_header(this_line):
            header = re.split(r'[0-9' + dash + '-]', this_line)[0].strip()
            continue
        if is_sale(this_line):
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
        html = io.read().decode('windows-1252')

    report = []
    pattern = re.compile(r'<table align="center" style="width: 80%">.*?</table>', flags=re.DOTALL)
    match = pattern.search(html)
    while match:
        report.append(match.group(0))
        pos = match.end()
        match = pattern.search(html, pos)

    ## hr = soup.find('img', attrs={'src': '_themes/canvas/acnvrule.gif'})
    ## report = report_generator(hr.find_next('table'))

    for this_report in report:

        this_report = BeautifulSoup(this_report)

        tr = this_report.find_all('tr')
        sale_date = get_sale_date(tr.pop(0))
        io_name = archive.new_csv(sale_date)

        #Stop iteration if this report is already archived
        if not io_name:
            continue

        # Initialize the default sale dictionary
        sale_head = None
        this_default_sale = default_sale.copy()
        this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                'sale_head': sale_head,
                })

        col = [list(td.strings) for td in tr.pop().find_all('td')]
        if tr:
            pass
        line = [re.sub(r'\s+', ' ', nested_item) for item in col for nested_item in item]

        # open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()

