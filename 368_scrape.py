import csv
from urllib.request import Request, urlopen
import re
from sys import argv, platform
from bs4 import BeautifulSoup
import dateutil.parser
from os import system
import scrape_util

default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'auction-results/'
temp_raw = scrape_util.ReportRaw(argv, prefix)
strip_char = ';,. \n\t\r'
    

def get_sale_date(date):
    date_string = date[-1]
    sale_date = dateutil.parser.parse(date_string, fuzzy = True)
    
    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""
    has_price = re.search(r'[0-9]+\.[0-9]{2}', str(this_line))
    is_not_succinct = (len(this_line) > 3)
    
    return bool(has_price and is_not_succinct)


def is_number(string):
    has_string = re.search(r'[1-9]',string)
    return bool(has_string)


def is_heading(this_line):
    has_heading = re.search(r'Fat|Fats|Feeders|Cows',str(this_line))
    is_succinct = len(this_line) < 3
    return bool(has_heading and is_succinct)


def get_sale_location(sale_location):
    """Convert address strings into a list of address components."""

    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')$', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def get_sale(this_line,cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    number_word = list(idx for idx in range(len(this_line)) if is_number(this_line[idx]))
    
    sale_list = this_line[0]
    sale_location = get_sale_location(sale_list)

    sale = {
        'consignor_city': sale_location.pop(0).title()
        }

    if sale_location:
        sale['consignor_state'] = sale_location.pop()

    cattle = cattle + ' ' + this_line[number_word[0]-1]
    sale.update({'cattle_cattle': cattle})
    
    weight_string = this_line[number_word[0]]
    sale.update({'cattle_avg_weight': weight_string})
    
    price_string = this_line[number_word[1]]
    price_string = price_string.replace(',','')
    price_string = price_string.replace('$','')
    sale.update({'cattle_price_cwt': price_string})
        
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    for idx, this_line in enumerate(line):
        if is_heading(this_line):
            cattle = ' '.join(this_line)
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line,cattle))
            writer.writerow(sale)
        elif this_line and this_line[-1] in ['VACCINATED', 'OPEN']:
            line[idx + 1] = this_line + line[idx + 1]


def main():
    
    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = soup.find_all('a', text='Market Report PDF')

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        request = Request(
            this_report['href'],
            headers = scrape_util.url_header,
            )
        
        this_default_sale = default_sale.copy()
        
        # create temporary text file from downloaded pdf
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))
        
        # read sale text into line list
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = [re.split(r'\s{2,}', this_line.strip()) for this_line in io.readlines()]
        temp_raw.clean()
        line = [this_line for this_line in line if this_line]

        sale_date = get_sale_date(line.pop(0))
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        io_name = archive.new_csv(sale_date)
        if not io_name:
            break
                    
        with io_name.open('w') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
