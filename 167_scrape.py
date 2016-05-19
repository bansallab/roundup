import csv
from os import system
import re
from urllib.request import Request, urlopen
from datetime import date
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
temp_raw = scrape_util.ReportRaw(argv, prefix)


def get_sale_date(report):
    """Return the date of the livestock sale."""

    match = re.search('([0-9]{1,2})-?([0-9]{1,2})-?([0-9]+)', report)
    if match:
        date_list = [int(match.group(idx)) for idx in [3, 1, 2]]
        date_list[0] += 2000
        sale_date = date(*date_list)
    else:
        sale_date = None

    return sale_date


def write_sale(line, default_sale, writer):

    header = None
    for this_line in line:
        if is_header(this_line):
            header = get_header(this_line)
        elif header and is_sale(this_line):
            sale = default_sale.copy()
            sale.update(get_sale(this_line, header))
            writer.writerow(sale)


def is_header(line):
    is_succinct = len(line) < 4
    return is_succinct


def get_header(line):
    new_header = ' '.join(line).strip()
    has_cattle = re.search(r'heifer|bull|steer|pair|cow', new_header, re.IGNORECASE)
    if has_cattle:
        header = new_header
    else:
        header = None
    return header


def is_sale(line):

    text = ''.join(line)
    match_range = re.search(r'\$[0-9\.\s]+-', text)
    match_price = '$' in text

    return match_price and not match_range


def get_sale(line, header):

    number_idx = [idx for idx, this_word in enumerate(line) if is_number(this_word)]

    sale_location = get_sale_location(line[0:number_idx[0]])

    sale = {
        'consignor_city': sale_location[0].title(),
        'consignor_state': sale_location[1],
        'cattle_head': line[number_idx[0]],
        'cattle_avg_weight': line[number_idx[1]].replace(',', ''),
        'cattle_cattle': ' '.join(line[number_idx[0] + 1:number_idx[1]] + [header]),
        }

    price_type = 'cattle_price_cwt' if 'cwt' in line[-1].lower() else 'cattle_price'
    sale[price_type] = line[number_idx[2]].strip('$').replace(',', '')

    sale = {k: v for k, v in sale.items() if v}

    return sale


def is_number(word):
    match = re.match(r'\$?\s*[0-9,\.]+#?$', word)
    return match


def get_sale_location(location):

    location = ' '.join(location)
    if ',' in location:
        sale_location = location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [location, '']

    return sale_location


def main():

    # locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # download Saturday sale page
    request = Request(
        base_url + '/saturday_sale.html',
        headers=scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())

    report = [
        a['href'] for a in soup.find_all('a')
        if 'pdf' in a['href'].lower()
        and 'special' not in a.get_text().lower()
        and re.search(r'\d', a['href'])
        ]

    for this_report in report:

        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)

        #Stop iteration if this report is already archived
        if not io_name:
            break

        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                })

        request = Request(
            base_url + this_report,
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = [[word.strip() for word in re.split(r'\s{2,}|(?<=\d)\s', this_line)] for this_line in io if this_line.strip()]
        temp_raw.clean()

        # open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
