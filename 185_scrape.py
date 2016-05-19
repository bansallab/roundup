import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
import dateutil.parser
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market_report'
temp_raw = scrape_util.ReportRaw(argv, prefix)
strip_char = ';,. \n\t'
to_float = re.compile(r'\$|,')
    

def get_sale_date(line):
    
    sale_date = None
    for this_line in line:
        match = re.search('DATE ?/ ?TIME:(.+)', ' '.join(this_line), re.IGNORECASE)
        if match:
            date_string = match.group(1)
            match = re.search(r'page', date_string, re.IGNORECASE)
            if match:
                date_string = date_string[:match.start()]
            sale_date = dateutil.parser.parse(date_string, fuzzy = True)
            break
        
    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""
    
    has_price = re.search(r'[0-9]+\.[0-9]{2}', str(this_line))
    is_not_succinct = (len(this_line) > 3)
    
    return bool(has_price and is_not_succinct)


def is_number(string):
    
    try:
        float(to_float.sub('', string))
    except ValueError:
        result = False
    else:
        result = True
    
    return result


def get_sale_location(sale_list):
    """Convert address strings into a list of address components."""

    state = sale_list[-1]
    city = ' '.join(sale_list[:-1])
    
    sale_location = [city, state]               
    
    return sale_location


def get_sale(this_line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    if this_line[2]=='M]':
        this_line[2:3] = ['MN', ']']

    number_word = list(
        idx for idx, val in enumerate(this_line)
        if is_number(val)
        )

    sale_list = this_line[1:number_word[0]-1]
    
    if sale_list:
        sale_location = get_sale_location(sale_list)
        sale = {
            'consignor_city': sale_location.pop(0).title(),
            'consignor_state': sale_location.pop(0), 
            }
    else:
        sale = {}
    
    head_string = this_line[number_word[0]]
    sale['cattle_head'] = head_string
    
    if number_word[1] - number_word[0] == 2:
        cattle = this_line[number_word[1]-1]
    elif number_word[1] - number_word[0] > 2:
        cattle = ' '.join(this_line[number_word[0]+1 : number_word[1]])
    else:
        cattle = ''

    if re.search(r'hogs?|goat|donkey|horse|tack|ewe|sheep|hay', cattle, re.IGNORECASE):
        return {}
    sale['cattle_cattle']= cattle

    weight_string = this_line[number_word[1]]
    sale['cattle_avg_weight'] = weight_string

    price_string = this_line[number_word[2]].replace(',', '')
    if 'H' == this_line[-1]:
        sale['cattle_price'] = price_string
    elif 'C' in this_line[-1]:
        sale['cattle_price_cwt'] = price_string

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line))
            if sale != this_default_sale:
                writer.writerow(sale)


def main():
    
    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = soup.findAll('a',{"type":"4"})
    
    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:

        if 'http' in this_report['href']:
            full_url = this_report['href']
        else:
            full_url = base_url + this_report['href']

        request = Request(
            full_url,
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
