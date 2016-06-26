import csv
import re
from urllib.request import Request, urlopen
from datetime import date
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'cattle-market/'


def get_sale_date(text):
    """Return the date of the livestock sale."""
    text = re.sub(r'\s\.(\d)', r'. \1', text)
    match = re.search(r'[\w\.]+[0-9\s]+,[0-9\s]+$', text)
    date_string = match.group(0)
    sale_date = dateutil.parser.parse(date_string).date()
    if sale_date==date.today():
        sale_date = None
    return sale_date


def get_sale_head(text):
    """Return the date of the livestock sale."""
    match = re.match(r'[0-9\s]+', text)
    head = match.group(0).strip()
    try:
        int(head)
    except ValueError:
        head = None
    return head


def is_heading(line):
    has_only_cattle = re.match('(steer|heifer)[^0-9]+$', line, re.IGNORECASE)
    return bool(has_only_cattle)


def is_sale(line):
    has_price = False
    has_dash = '\u2013' in line
    has_dash |= '-' in line
    if has_dash:
        match = re.search(r'[0-9]\.[0-9]{2}$', line)
        has_price = bool(match)
    return has_price


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


def get_sale(line, heading):

    match = re.search(r'(?P<head>[0-9]+)[^0-9]+(?P<weight>[0-9]+)#(?P<location>[^0-9]+)(?P<price>[0-9\.]+)', line)
    if not match:
        match = re.search(r'(?P<head>[0-9]+).*?(–|-)(?P<location>[^0-9]+)(?P<price>[0-9\.]+)', line)
    match = match.groupdict()

    sale_location = get_sale_location(match['location'])

    sale = {
        'consignor_city': sale_location[0].title(),
        'consignor_state': sale_location[1].upper(),
        'cattle_head': match['head'],
        'cattle_cattle': heading,
        'cattle_avg_weight': match.get('weight'),
        'cattle_price_cwt': match['price'],
        }

    sale = {k: v.strip('. ') for k, v in sale.items() if v}
    return sale


def write_sale(line, default_sale, writer):

    heading = None
    for this_line in line:
        if is_heading(this_line):
            heading = this_line.strip(':')
        elif heading and is_sale(this_line):
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
        soup = BeautifulSoup(io.read(), 'lxml')
    # div = soup.find(id='content')
    div = soup.find('div', attrs={'class':'entry-content'})
    p = div.p
    p_text = p.get_text().strip()
    report = [[]]
    while p_text:
        report[-1].append(p_text)
        p = p.find_next_sibling('p')
        p_text = p.get_text().strip()
        if '___' in p_text:
            p = p.find_next_sibling('p')
            p_text = p.get_text().strip()
            if p_text:
                report.append([])

    for this_report in report:

        line = [line.replace('\xa0', '') for line in this_report]

        date_and_head = line.pop(0)
        if re.match(r'Slaughter', date_and_head):
            continue
        date_string, head_string = tuple(re.split(r'(?<=\d)\s*[-\u2013]', date_and_head, maxsplit=1))
        sale_date = get_sale_date(date_string)
        io_name = archive.new_csv(sale_date)

        #Stop iteration if this report is already archived
        if not io_name:
            continue

        # Initialize the default sale dictionary
        sale_head = get_sale_head(head_string)
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


if __name__ == '__main__':
    main()
