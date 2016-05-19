import csv
from urllib.request import Request, urlopen
import dateutil.parser
from datetime import date
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'Markets.html'
strip_char = ';,. \n\t'


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    is_not_succinct = len(this_line.split()) > 3
    has_price = re.search(r'[0-9]+\.[0-9]{2}', this_line)

    return bool(has_price and is_not_succinct)


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-]|/.+$|cwt|pr|he?a?d?', '', string, flags=re.IGNORECASE)
    try:
        float(string)
    except ValueError:
        is_number = False
    else:
        is_number = True

    return is_number


def get_sale_location(line):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(line)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')$', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def get_sale(line, last_consignor):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    word = line.split()
    number_idx = [idx for idx, val in enumerate(word) if is_number(val)]

    if number_idx[0] > 0:
        sale_location = get_sale_location(word[:number_idx[0]])
        sale = {
            'consignor_city': sale_location.pop(0).strip(strip_char).title(),
            }
        if sale_location:
            sale['consignor_state'] = sale_location.pop().strip(strip_char)
    else:
        sale = last_consignor

    cattle_string = ' '.join(word[number_idx[0]+1:number_idx[1]])
    sale['cattle_cattle'] = cattle_string.strip(strip_char)

    head_string = word[number_idx[0]].strip(strip_char).replace(',', '')
    try:
        float(head_string)
        sale['cattle_head'] = head_string
    except ValueError:
        pass

    weight_string = word[number_idx[1]].strip(strip_char).replace(',', '')
    try:
        int(weight_string)
    except ValueError:
        pass
    else:
        sale['cattle_avg_weight'] = weight_string

    if len(number_idx) < 3 and '$' in weight_string:
        price_string = word[number_idx[1]]
        if 'pair' in sale['cattle_cattle']:
            price_string += '/hd'
    else:
        price_string = word[number_idx[2]]
    match = False
    if not match:
        match = re.search(r'([0-9,.]+)/?(pr|he?a?d)', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+)/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)

    sale = {k:v for k,v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    last_consignor = {}
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line, last_consignor))
            last_consignor = {k: v for k, v in sale.items() if 'consignor_' in k}
            writer.writerow(sale)


def get_sale_date(this_report):
    """Return the date of the sale."""

    text = this_report.get_text().strip().replace('\xa0','')
    date_string = re.split(r'\s{2,}', text)[0]
    if re.match(r'next', date_string, re.IGNORECASE):
        return None
    sale_date = dateutil.parser.parse(date_string, fuzzy=True).date()
    if sale_date >= date.today():
        sale_date = None
    return sale_date


def main():            

    # Collect individual reports into a list
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())

    report = soup.find_all('td', attrs={'colspan': 4})

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:
    
        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            continue
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # List each line of the report
        line = [p.get_text().replace('\xa0','') for p in this_report.find_all('p')]

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
