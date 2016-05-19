import csv
from urllib.request import Request, urlopen, urlretrieve
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
from os import system
import scrape_util
from datetime import datetime, timedelta


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/Market_Report.html'
strip_char = ';,. \n\t'
temp_raw = scrape_util.ReportRaw(argv, prefix, suffix='jpg')


def get_sale_date(this_report):
    """Return the date of the livestock sale."""

    div = this_report.find_all('div')
    for this_div in div:
        if this_div.string:
            match = re.search(r'([0-9]+)\s*-\s*([0-9]+)\s*-\s*([0-9]+)', this_div.string)
            if match:
                date_string = match.group()
                break
    sale_date = dateutil.parser.parse(date_string)
    return sale_date


def is_heading(this_line):
    """Determine whether a given line is a section header 
    that describes subsequent lines of a report.
    """

    cattle_clue = '(bulls?|steers?|cows?|heiferettes?|heifers?|calves|pairs?)'
    has_cattle = re.search(cattle_clue, this_line, re.IGNORECASE)
    is_succinct = len(re.split(r'\s{3,}',this_line)) < 3
   
    return bool(has_cattle and is_succinct)
    

def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = re.search(r'[0-9]+', this_line)
    is_not_succinct = len(re.split(r'\s{3,}',this_line)) > 3
    
    return bool(has_price and is_not_succinct)


def is_number(string):
    """Test whether a string is numeric. Ignoring units like 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-/ ]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    string = re.sub(r'o', '0', string, flags=re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale(word, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    
    number_word = list(idx for idx in range(len(word)) if is_number(word[idx].strip('_')))

#    name_string = re.sub(r"(\w)(?=[A-Z])", r"\1 ", word[0])
#    city_string = re.sub(r"(\w)(?=[A-Z])", r"\1 ", word[1])
    name_string = word[0]
    city_string = word[1]
    sale = {
        'consignor_city': city_string.strip(strip_char).title(),
        'consignor_name': name_string.strip(strip_char),
        }

    head_cattle_string = word[2].replace(' ', '')
    cattle_match = re.match(r'([0-9]+)(.+)', head_cattle_string)
    if cattle_match:
        sale['cattle_cattle'] = ' '.join([cattle_match.group(2).strip(strip_char), cattle]).strip(strip_char)
        sale['cattle_head'] = cattle_match.group(1).strip(strip_char)

    price_string = word[number_word.pop()].replace(' ','')
    price_string = re.sub(r'o', '0', price_string, flags=re.IGNORECASE)
    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',','').strip(strip_char)

    if number_word:
        weight_string = word[number_word.pop()].strip(strip_char).replace(',', '').replace(' ','')
        weight_string = re.sub(r'o', '0', weight_string, flags=re.IGNORECASE)
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass

    sale = {k:v for k, v in sale.items() if v}
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    cattle = ''
    for this_line in line:
        if is_heading(this_line):
            cattle = this_line.strip(strip_char)
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            word = re.split(r'\s{2,}',this_line)
            sale.update(get_sale(word, cattle))
            writer.writerow(sale)


def main():            
    
    # Get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
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

        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # Convert jpg report to txt and read into line
        img_path = this_report.find('div', id = 'wb_Image1').find('img')['src'].replace(' ', '%20')
        img_url = base_url + img_path
        urlretrieve(img_url, str(temp_raw))
        temp_txt = temp_raw.with_suffix('.txt')
        system(scrape_util.tesseract.format("-c preserve_interword_spaces=1", str(temp_raw), str(temp_txt.with_suffix(''))))
        with temp_txt.open('r') as io:
            line = list(this_line.strip() for this_line in io)
        temp_raw.clean()
        
        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


def catchup():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    report = temp_raw.folder.glob('*.jpg')
    for this_report in report:

        sale_date = datetime.fromtimestamp(this_report.stat().st_ctime).date()
        while sale_date.weekday() != 4: ## Friday Sales
            sale_date = sale_date - timedelta(days=1)
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

        # Convert jpg report to txt and read into line
        temp_txt = temp_raw.with_suffix('.txt')
        system(scrape_util.tesseract.format("-c preserve_interword_spaces=1", str(this_report), str(temp_txt.with_suffix(''))))
        with temp_txt.open('r') as io:
            line = list(this_line.strip() for this_line in io)
        
        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
