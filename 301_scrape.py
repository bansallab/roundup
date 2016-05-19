import csv
from urllib.request import Request, urlopen
import dateutil.parser
from datetime import date
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'actual-sales-from-this-week/'
strip_char = ';,. \n\t\xa0'


def get_sale_date(content):
    """Return the date of the sale."""
    
    date_string = content.find_all('div')[1].get_text()
    
    match = re.search(r'(\d+)\s*(and|&)\s*(\d+)', date_string)
    if match:
        date_string = [date_string.replace(match.group(0), match.group(idx)) for idx in [1, 3]]
    else:
        date_string = [date_string]
    sale_date = [dateutil.parser.parse(this_string, fuzzy=True).date() for this_string in date_string]
    if sale_date[-1] == date.today():
        sale_date = []

    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    td = this_line.find_all('td')
    is_not_succinct = len(td) > 2
    has_number = False
    for td in td:
        if td.get_text():
            if is_number(td.get_text()):
                has_number = True
                break
    
    return bool(has_number and is_not_succinct)


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


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/]|c?wt|cw?t|he?a?d?|l?bs|bls|phd|ppr?|pph|lbs/each', '', string, flags = re.IGNORECASE)
        string = string.replace('oo','00')
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
    
    sale_location = get_sale_location(word[0:1])
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        }
                
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    cattle_string = word[1].strip(strip_char)
    cattle_match = re.match(r'([0-9,]+)(.+)', cattle_string)
    if cattle_match:
        sale['cattle_head'] = cattle_match.group(1).replace(',','').strip(strip_char)
        sale['cattle_cattle'] = cattle_match.group(2).strip(strip_char)
    else:
        sale['cattle_cattle'] = cattle_string

    weight_string = re.sub(r'[^0-9]', '', word[number_word[0]])
    sale['cattle_avg_weight'] = weight_string

    price_string = word[number_word[1]].replace('oo','00')
    match = False
    if not match:
        match = re.search(r'([0-9,\.\s]+)(/?he?a?d?|/?phd|/?ppr|/?pph)', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,\.\s]+)/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)
        
    sale = {k: v for k, v in sale.items() if v}
    
    return sale


def is_correct_date(line, correct_date):

    is_correct_date = True
    text = line.td.get_text()
    match = re.search(r'([0-9]{1,2}/[0-9]{1,2})', text)
    if match and correct_date != match.group(1):
        is_correct_date = False

    return is_correct_date


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    correct_date = '{}/{}'.format(this_default_sale['sale_month'], this_default_sale['sale_day'])

    wrote = []
    for idx, this_line in enumerate(line):
        if is_sale(this_line) and is_correct_date(this_line, correct_date):
            wrote.append(idx)
            sale = this_default_sale.copy()
            word = [td.get_text().strip() for td in this_line.find_all('td')]
            word[0] = word[0].replace(correct_date, '').strip()
            sale.update(get_sale(word))
            writer.writerow(sale)
    for idx in reversed(wrote):
        line.pop(idx)

    return line


def main():            

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Collect individual reports into a list
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())

    content = soup.find('div', id = 'matrix_44243504')
    table = content.find('div', attrs={'class':'tableContainer'}).find('table')
    line = table.find_all('tr')
    report = get_sale_date(content)

    # Write a CSV file for each report not in the archive
    for this_report in report:
    
        sale_date = this_report
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break

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
            line = write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
