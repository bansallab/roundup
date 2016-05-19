import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
import dateutil.parser
from os import system
import scrape_util
from datetime import date


default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t\r'
temp_raw = scrape_util.ReportRaw(argv, prefix)


def get_sale_date(line):

    date_string = ' '.join(line[2][-3:])
    sale_date = dateutil.parser.parse(date_string, fuzzy=False).date()
    if sale_date >= date.today():
        sale_date = None
    
    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = re.search(r'[0-9]+\.[0-9]{2}', str(this_line))
    is_not_succinct = (len(this_line) > 3)
    is_not_cattle = re.search(r'hog|sheep|goat', str(this_line), re.IGNORECASE)
    
    return bool(has_price) and is_not_succinct and not bool(is_not_cattle)


def is_number(string):
    has_string = re.search(r'[1-9]',string)
    return bool(has_string)


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + '$)', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def get_sale(this_line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    number_word = list(idx for idx in range(len(this_line)) if is_number(this_line[idx]))
    
    sale_list = this_line[:number_word[0]]
    sale_location = get_sale_location(sale_list)

    sale = {
        'consignor_city': sale_location.pop(0).title(),
        }

    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)
    
    if number_word[1] - number_word[0] == 2:
        cattle = this_line[number_word[1]-1]
    elif number_word[1] - number_word[0] > 2:
        cattle = ' '.join(this_line[number_word[0]+1 : number_word[1]])
    else:
        cattle = ''
        
    sale.update({'cattle_cattle': cattle})

    head_string = this_line[number_word.pop(0)]
    sale.update({'cattle_head':head_string})

    price_string = this_line[number_word.pop()].replace(',','')

    if number_word:
        weight_string = this_line[number_word.pop()]
        sale.update({'cattle_avg_weight': weight_string})

    if this_line[-1] == "C":
        sale.update({'cattle_price_cwt': price_string})

    elif this_line[-1] == "H":
        sale.update({'cattle_price': price_string})
        
    sale = {k: v.strip() for k, v in sale.items() if v.strip()}
        
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    for idx, this_line in enumerate(line):
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line))
            writer.writerow(sale)
        elif this_line and this_line[-1] in ['VACCINATED', 'OPEN']:
            line[idx + 1] = this_line + line[idx + 1]


def main():

    # Location of existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # get URLs for all reports
    request = Request(
        base_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = soup.find_all('a', text='Market Report PDF')

    # write csv file for each historical report
    for this_report in report:

        request = Request(
            '/'.join(base_url.split('/')[:3]) + this_report['href'],
            headers = scrape_util.url_header,
            )
        
        # create temporary text file from downloaded pdf
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))
        
        # read sale text into line list
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = [this_line.strip(strip_char).split() for this_line in io.readlines()]
        temp_raw.clean()
        line = [this_line for this_line in line if this_line]

        sale_date = get_sale_date(line)
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })
                            
        with io_name.open('w') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
