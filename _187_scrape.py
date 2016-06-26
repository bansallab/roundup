import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util
 

default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/market%20report.html'
strip_char = ';,. \n\t'


def get_sale_date(this_report):
    """Return the date of the sale."""
    
    date_string = this_report['href'].split('/')[1]
    date_string = date_string.replace('.html','')
    sale_date = dateutil.parser.parse(date_string)

    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    td = this_line.find_all('td')
    is_not_succinct = len(td) > 3
    has_price = False
    for td in td:
        if re.search(r'[0-9]+\.[0-9]{2}', td.get_text()):
            has_price = True
            break
    
    return bool(has_price and is_not_succinct)


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
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

    cattle_string = word[number_word[0]+1]

    # Skip lines describing sales of non-cattle
    if re.search(r'lamb|ewe',cattle_string, re.IGNORECASE):
        return {}

    consignor_name = word[0].strip(strip_char)
    if re.match(r'consignment +of', consignor_name, re.IGNORECASE):
        consignor_name = ''

    sale = {
        'consignor_name': consignor_name.title()
    }

    weight_match = re.search(r'\(([0-9,]+)#\)',cattle_string)
    if weight_match:
        weight_string = weight_match.group(1).replace(',', '')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass
        cattle_string = cattle_string.replace(weight_match.group(),'')

    sale['cattle_cattle'] = re.sub(r'[\r\n\t]', '', cattle_string).strip(strip_char)

    price_string = word[number_word.pop()]

    head_string = word[number_word.pop(0)].strip(strip_char).replace(',', '')
    try:
        int(head_string)
        sale['cattle_head'] = head_string
    except ValueError:
        pass

    # Price key depends on the existence of weight string
    if number_word:
        weight_string = word[number_word.pop()].strip(strip_char).replace(',', '')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass
        key = 'cattle_price_cwt'
    else:
        key = 'cattle_price'

    match = re.search(r'([0-9,.]+)', price_string, re.IGNORECASE)
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)
        
    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = []
            for td in this_line.find_all('td'):
                word.append(td.get_text().replace('\xa0',''))
            if word[0].strip() == '':
                word[0] = consignor_name
            else:
                consignor_name = word[0]
            sale.update(get_sale(word))
            if sale != this_default_sale:
                writer.writerow(sale)


def main():            
    
    # Collect individual reports into a list
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')

    a_tag = soup.find_all('a')
    report = []
    for this_a in a_tag:
        if re.match(r'market(%20)?[0-9]{4}', this_a['href']):
            report.append(this_a)

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

        request = Request(
            base_url + this_report['href'],
            headers = scrape_util.url_header,
        )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read(), 'lxml')

        table = soup.find_all('table', id = re.compile('table[0-9]+'))
        # List each line of the report
        line = []
        for this_table in table:
            line += this_table.find_all('tr')

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
