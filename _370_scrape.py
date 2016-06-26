import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
import dateutil.parser
from os import system
from datetime import date
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'auction-results'
strip_char = ';,. \n\t\r'
temp_raw = scrape_util.ReportRaw(argv, prefix)
    

def get_sale_date(line):
    date_string = ' '.join(line)
    sale_date = dateutil.parser.parse(date_string, fuzzy=True).date()
    if sale_date >= date.today():
        sale_date = None
    
    return sale_date
# def get_sale_date(a):

#     date_string = ' '.join(list(a.stripped_strings))
#     sale_date = dateutil.parser.parse(date_string, fuzzy=True)
    
#     return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = re.search(r'[0-9]+\.[0-9]{2}', str(this_line))
    is_not_succinct = (len(this_line) > 2)
    
    return bool(has_price and is_not_succinct)


def is_number(string):
    string = re.sub(r'\$|,|\.', '', string)
    all_digits = re.match(r'[0-9]+$',string)
    return bool(all_digits)


def get_heading(this_line):

    heading = ''
    price_type = ''
    is_succinct = len(this_line) < 4
    if is_succinct:
        this_line = ' '.join(this_line)
        has_heading = re.search(r'HEIFER|FEEDER|SLAUGHTER|HOLSTEINS|BULLS|CALVES|SPRINGERS|DAIRY HERD|FAT BEEF|FAT HOL|OPEN HOL', this_line)
        hd_match = re.search(r'HD$', this_line)
        if has_heading and hd_match:
            heading = this_line.replace(hd_match.group(0), '').strip(strip_char)
            price_type = 'cattle_price'
        elif has_heading:
            heading = this_line.strip(strip_char)
            price_type = 'cattle_price_cwt'

    return heading, price_type


def get_sale_location(sale_list):
    """Convert address strings into a list of address components."""
    if len(sale_list)== 1:
        state = ''
        city = sale_list[0]
    elif len(sale_list) > 1:
        city = ' '.join(sale_list)
        state = ''
    else:
        city = ''
        state = ''
    name = ''
    
    sale_location = [name, city, state]
                              
    return sale_location


def get_sale(this_line, cattle, price_type):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    number_word = list(idx for idx in range(len(this_line)) if is_number(this_line[idx]))
    
    sale_list = [this_line[0]]
    sale_location = get_sale_location(sale_list)

    sale = {
        'consignor_name': sale_location.pop(0),
        'consignor_city': sale_location.pop(0).strip().title(),
        'consignor_state': sale_location.pop(0), 
        }
    
    cattle = cattle + ' ' + ' '.join(this_line[1:number_word[0]])
    sale['cattle_cattle'] = cattle

    head_string = this_line[number_word[0]]
    sale['cattle_head'] = head_string

    if len(number_word)==3:
        weight_string = this_line[number_word[1]] if this_line[number_word[1]]!='0' else ''
        price_string = this_line[number_word[2]]
    elif len(number_word)==2:
        weight_string = ''
        price_string = this_line[number_word[1]]

    price_string = price_string.replace(',', '')
    price_string = price_string.replace('$', '')
    sale['cattle_avg_weight'] = weight_string

    if 'cwt' in price_type and not weight_string:
        price_type = 'cattle_price'
    sale[price_type] = price_string
    
    sale = {k: v.strip() for k, v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    for idx, this_line in enumerate(line):
        heading, price_type = get_heading(this_line)
        if heading:
            cattle = heading
            cattle_price = price_type
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line, cattle, cattle_price))
            writer.writerow(sale)
        elif this_line and this_line[-1] in ['VACCINATED', 'OPEN']:
            line[idx + 1] = this_line + line[idx + 1]


def main():
    
    # get URLs for all reports
    request = Request(
        base_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = soup.find_all('a', text='Market Results PDF')

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        request = Request(
            this_report["href"],
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
            line = [re.split(r' {2,}', this_line.strip(strip_char)) for this_line in io.readlines()]
        temp_raw.clean()
        line = [this_line for this_line in line if this_line]

        sale_date = get_sale_date(line.pop(0))
        io_name = archive.new_csv(sale_date)
        if not io_name:
            break

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
