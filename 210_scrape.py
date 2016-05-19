import csv
from urllib.request import Request, urlopen
from datetime import date, timedelta
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util
 

default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/cattle-sales/market-report'
strip_char = ';,. \n\t'
#match_description = re.compile(r', ?([a-z]+ ?[0-9]+ ?, ?[0-9]+)', re.IGNORECASE)
match_description = re.compile(r'sold(.*?\d+[,\s]+\d+)', re.IGNORECASE)


def get_sale_date(sale_description):
    """Return the date of the sale."""

    if sale_description:
        match = match_description.search(sale_description)
        if match:
            sale_date = dateutil.parser.parse(match.group(1))
    else:
        ## default to last Wednesday
        date_difference = (date.today().weekday() - 1 - 2) % 7 + 1
        sale_date = date.today() - timedelta(date_difference)

    return sale_date


def get_sale_head(sale_description):
    """Return the total number of head sold at the sale.
    If present, the number is usually at the top of the market report."""

    if sale_description:
        match = re.search(r'([0-9,]+)\s*(head|cattle)', sale_description, re.IGNORECASE)
        if match:
            sale_head = match.group(1).replace(',', '')
    else:
        sale_head = ''

    return sale_head


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    td = this_line.find_all('td')
    is_not_succinct = len(td) > 3
    has_price = False
    for td in td:
        if td.string:
            if re.search(r'[0-9]+\.[0-9]{2}', td.string):
                has_price = True
                break

    return bool(has_price and is_not_succinct)


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + r')$', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/]|(cw?t?)|(he?a?d?)', '', string, flags = re.IGNORECASE)
        try:
            float(string)
            result = True
        except ValueError:
            result = False
    else:
        result = False

    return result


def get_sale(word):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """


    number_word = [idx for idx, val in enumerate(word) if is_number(val)]

    sale_location = get_sale_location(word[0:number_word[0]])

    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_cattle': ' '.join(word[number_word[0]+1:number_word[1]]),
        }

    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    head_string = word[number_word.pop(0)].strip(strip_char).replace(',', '')
    try:
        int(head_string)
        sale['cattle_head'] = head_string
    except ValueError:
        pass

    price_string = word[number_word.pop()]

    if number_word:
        weight_string = word[number_word.pop()].strip(strip_char).replace(',', '')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass
        orig_key = 'cattle_price_cwt'
    else:
        orig_key = 'cattle_price'

    match = False
    if not match:
        match = re.search(r'([0-9,.]+)\s*/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+)\s*/?cw?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if not match:
        match = re.search(r'([0-9,.]+)', price_string, re.IGNORECASE)
        key = orig_key
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)

    sale = {k:v for k,v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = list(this_line.stripped_strings)
            sale.update(get_sale(word))
            writer.writerow(sale)


def main():

    # Collect individual reports into a list
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
    
        main_table = this_report.find('table')
        sale_description = main_table.find(text=match_description)
        sale_description = sale_description.find_parent('td').get_text()
        sale_date = get_sale_date(sale_description)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        sale_head = get_sale_head(sale_description)
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        content_table = main_table.find('table')

        # List each line of the report
        line = content_table.find_all('tr')

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
