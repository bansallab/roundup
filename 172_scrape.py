import csv
from urllib.request import Request, urlopen
import re
from sys import argv, platform
from bs4 import BeautifulSoup
import dateutil.parser
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/MarketReport.html'
strip_char = ';,. \n\t@'
temp_raw = scrape_util.ReportRaw(argv, prefix)


def get_sale_date(this_report):

    date_string = this_report.get_text()
    date_string = date_string.split()[0]
    sale_date = dateutil.parser.parse(date_string, fuzzy = True)
        
    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""
    
    has_price = re.search(r'\$+[0-9]+\.[0-9]{2}', str(this_line))
    is_not_succinct = (len(this_line) > 3)
    
    return bool(has_price and is_not_succinct)


def is_location (this_line):

    has_location = re.search(scrape_util.state, str(this_line))

    return bool(has_location)


def is_sale_head(this_line):

    has_sale_head = re.search(r'HEAD?',str(this_line))

    return bool(has_sale_head)


def is_number(string):
    
    has_string = re.search(r'^[0-9,\.\$]+$', string)
    
    return bool(has_string)


def get_sale_head(this_line):

    sale_head = {'sale_head':this_line[0]}
    
    return sale_head


def get_sale_location(this_line):
    """Convert address strings into a list of address components."""

    state = this_line[-1]
    city = this_line[-2].replace(',','')
    
    sale_location = {
            'consignor_city': city,
            'consignor_state': state
            }
    
    return sale_location


def get_sale(this_line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    this_line = [ i.replace('@','').replace('-','') for i in this_line]
    number_word = list(
        idx for idx, val in enumerate(this_line)
        if is_number(val)
        )

    sale_list = this_line[number_word[-3]:]
        
    head_string = this_line[number_word[-3]]
    sale = {'cattle_head' : head_string}
    
    if number_word[-2] - number_word[-3] == 2:
        cattle = this_line[number_word[-3]+1]
    elif number_word[-2] - number_word[-3] > 2:
        cattle = ' '.join(this_line[number_word[-3]+1 : number_word[-2]])
    else:
        cattle = ''
    
    sale['cattle_cattle']= cattle

    weight_string = this_line[number_word[-2]]
    sale['cattle_avg_weight'] = weight_string

    price_string = this_line[number_word[-1]].replace(',', '')
    price_string = price_string.replace('$','')
    price_float = float(price_string) * 100
    sale['cattle_price_cwt'] = '{:.2f}'.format(price_float)

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale_head(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale_head(this_line))
        if is_sale(this_line):
            sale.update(get_sale(this_line))
        if is_location(this_line):
            sale.update(get_sale_location(this_line))
            writer.writerow(sale)


def main():
    
    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = soup.find('div',{'id':'ESW_GEN_ID_3'})
    report = report.findAll('a')

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:

        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        request = Request(
            base_url + this_report['href'],
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
