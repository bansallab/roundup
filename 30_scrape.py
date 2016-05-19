import csv
from urllib.request import Request, urlopen
import urllib.error
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util

default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t$'


def get_sale_head(line):

    head_string = line.pop().replace('hd','').strip(strip_char)
    try:
        sale_head = int(head_string)
        return sale_head
    except ValueError:
        return None


def get_sale_date(line):

    date_string = line[0].replace('Sale', '').strip(strip_char)
    sale_date = parser.parse(date_string)

    return sale_date


def is_sale(line, io_name):

    right_columns = line[0] and all(line[2:])
    has_price = '$' in ''.join(line[2:])
    extra_price = '$' in line[1]

    return (right_columns and has_price and not extra_price)


def get_sale_location(string):

    if ',' in string:
        sale_location = string.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', string)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [string]

    return sale_location


def get_sale(word, cattle):

    sale_location = get_sale_location(word[0])
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_cattle': cattle,
        'cattle_head': word[1].replace('hd', '').strip(strip_char),
        'cattle_avg_weight': word[2].strip(strip_char),
        }
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)
    try:
        cattle_head = int(sale['cattle_head'])
    except ValueError:
        sale['cattle_cattle'] = ' '.join([sale['cattle_cattle'], sale['cattle_head']])
        sale['cattle_head'] = ''

    price_word = re.sub(r'\([^\)]*\)?', '', word[3])
    match = re.search(r'/?(by the )?h[ea]{2}d', price_word, re.IGNORECASE)
    if match:
        price = 'cattle_price'
    else:
        price = 'cattle_price_cwt'
    sale[price] = re.search(r'[0-9,]+', price_word).group(0).replace(',', '')

    sale = {k:v for k,v in sale.items() if v}

    return sale


def main():

    # get URLs for all reports
    request = Request(
        base_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    google_doc = soup.iframe
    report = [google_doc]

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        # query this_report for sale data
        url = this_report['src']
        request = Request(
            url,
            headers = scrape_util.url_header,
            )
        try:
            with urlopen(request) as io:
                soup = BeautifulSoup(io.read(), 'lxml')
        except urllib.error.HTTPError:
            print('HTTP error: {}'.format(url))
            continue
        line = [
            [td.get_text().replace('\xa0', ' ') for td in tr.find_all('td')]
            for tr in soup.find_all('tr')
            ]

        sale_date = get_sale_date(line[0])

        # skip if already archived
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        # sale defaults
        sale_head = get_sale_head(line.pop(0))
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            # extract & write sale dictionary
            for this_line in line:
                if is_sale(this_line, io_name.name):
                    sale = this_default_sale.copy()
                    sale.update(get_sale(this_line, cattle))
                    if sale != this_default_sale:
                        writer.writerow(sale)
                else:
                    cattle = this_line[0].strip(strip_char)


if __name__ == '__main__':
    main()
