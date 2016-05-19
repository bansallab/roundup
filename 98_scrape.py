import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
from datetime import date
import scrape_util
 

default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'marketcards.htm'
strip_char = ';,. \n\t'


def get_sale_date(report):
    """Return the date of the livestock sale."""

    sale_date = None
    for pre in report.find_all('pre'):
        text = pre.get_text().strip().splitlines()
        while text:
            date_string = text.pop(0)
            if re.search(r'\d', date_string):
                sale_date = dateutil.parser.parse(date_string, fuzzy=False).date()
        if sale_date:
            break

    return sale_date


def get_sale_head(report):
    """Return the total number of cattle sold, from top of market report."""

    sale_head = None
    for pre in report.find_all('pre'):
        match = re.search(r'([0-9,]+)\s*(head|cattle)', pre.get_text(), re.IGNORECASE)
        if match:
            sale_head = match.group(1).replace(',', '')
            break

    return sale_head


def is_heading(this_line):
    """Determine whether a given line is a section header 
    that describes subsequent lines of a report.
    """
    cattle_clue = '(HEIFERS?|STEERS?)'
    has_cattle = re.search(cattle_clue, str(this_line), re.IGNORECASE)
    is_succinct = (len(this_line) <= 3 and len(this_line[0]) < 10)
    
    return bool(has_cattle and is_succinct)


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = re.search(r'[,0-9]+\.[0-9]{2}', this_line[-1])
    is_not_succinct = len(this_line) > 3
    has_range = re.search(r'[0-9]-[0-9]\.[0-9]{2}', ' '.join(this_line))
    has_dash = re.search(r'(-|' + b'\xe2\x80\x93'.decode() + r')', ' '.join(this_line))

    return bool(has_price) and is_not_succinct and not (bool(has_range) or bool(has_dash))


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def get_sale(this_line, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    sale = {'cattle_cattle': cattle}

    parens = re.compile(r'\([^\)]*\)')
    for idx, word in enumerate(this_line):
        match = parens.search(word)
        if match:
            sale['cattle_cattle'] += ' ' + match.group(0)
            new_word = this_line[idx].replace(match.group(0), ' ').strip().split()
            this_line.pop(idx)
            if new_word:
                this_line[idx:idx] = new_word
            break

    price_string = this_line.pop().strip()
    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = re.sub(r'[^0-9.]', '', match.group(1))

    weight_string = re.sub(r'[^0-9.]', '', this_line.pop())
    sale['cattle_avg_weight'] = weight_string

    sale_location = get_sale_location(this_line)
    sale['consignor_city'] = sale_location.pop(0).title().strip()
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip()

    sale = {k: v.strip() for k, v in sale.items() if v}
    return sale


def write_sale(lines, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in lines:
        if is_heading(this_line):
            cattle = this_line[0]
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line, cattle))
            writer.writerow(sale)


def main():            
    
    # Get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = [soup]
    

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break

        # Total number of head sold
        sale_head = get_sale_head(this_report)

        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # Read the report text into a list of lines
        line = []
        for this_line in this_report.find_all('pre'):
            span = this_line.find_all('span')
            this_line = [this_span.get_text().replace('\xa0', ' ') for this_span in span]
            this_line = [i.strip() for i in this_line if i.strip()]
            this_line = [b for a in this_line for b in a.split()]
            if this_line:
                line.append(this_line)

        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)
        

if __name__ == '__main__':
    main()
