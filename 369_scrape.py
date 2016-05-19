import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
import dateutil.parser
from datetime import date
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t\r'
temp_raw = scrape_util.ReportRaw(argv, prefix)
# # to replace from raw
# from pathlib import Path
# base_url = 'file://{}'.format(Path('long_prairie_scrape/pdf').absolute())
    

def get_sale_date(line):
    date_string = ' '.join(line)
    sale_date = dateutil.parser.parse(date_string, fuzzy=True).date()
    if sale_date >= date.today():
        sale_date = None
    
    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""
    has_cattle = re.search(r'hol|beef|jers|horn|xbred|bull|hfr|str', ' '.join(this_line), re.IGNORECASE)
    has_number = re.search(r'\b[0-9]+\b', ' '.join(this_line))
    is_not_succinct = len(this_line) > 2
    
    return bool(has_cattle) and bool(has_number) and is_not_succinct


def is_number(string):
    has_string = re.search(r'[1-9]',string)
    return bool(has_string)


def is_heading(this_line):
    has_cattle = re.search(r'Slaughter|Feeders?|Fats?|Cows?|Bulls?|Springer|Calf', ' '.join(this_line), re.IGNORECASE)
    has_number = re.search(r'\b[0-9]+\b', ' '.join(this_line))
    is_succinct = len(this_line) <= 3
    if has_cattle and not is_succinct:
        is_succinct = this_line[-1].strip() == '$'

    return bool(has_cattle) and not bool(has_number) and is_succinct


def get_sale(this_line, cattle, price_key):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    number_word = list(idx for idx in range(len(this_line)) if is_number(this_line[idx]))

    sale = {
        'consignor_city': this_line[0].strip(strip_char).title(),
        }

    if len(number_word) < 2:
        cattle = cattle + ' ' + ' '.join(this_line[1:number_word[0]])
        sale['cattle_cattle'] = cattle
        price_idx = number_word[0]
    elif number_word[0] + 1 == number_word[1]:
        cattle = cattle + ' ' + this_line[number_word[0] - 1]
        sale['cattle_cattle'] = cattle

        weight_string = this_line[number_word[0]]
        sale['cattle_avg_weight'] = weight_string

        price_idx = number_word[1]            
    else:
        cattle = cattle + ' ' + ' '.join(this_line[number_word[0]+1:number_word[1]])
        sale['cattle_cattle'] = cattle

        head_string = this_line[number_word[0]]
        sale['cattle_head'] = head_string

        if len(number_word) == 2:
            price_idx = number_word[1]
        else:
            weight_string = this_line[number_word[1]]
            sale['cattle_avg_weight'] = weight_string
            price_idx = number_word[2]

    price_string = this_line[price_idx]
    price_string = re.sub(r'[^0-9\.]', '', price_string)
    if price_key:
        sale[price_key] = price_string
    else:
        sale['cattle_price_cwt'] = price_string

    sale = {k: v.strip() for k, v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    for idx, this_line in enumerate(line):
        if is_heading(this_line):
            if re.search(r'head', this_line[-1], re.IGNORECASE):
                this_line.pop()
                price_key = 'cattle_price'
            else:
                price_key = None
            cattle = re.sub(r'weight|report', '', ' '.join(this_line), flags=re.IGNORECASE).strip()
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line,cattle, price_key))
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
        soup = BeautifulSoup(io.read())
    report = soup.find_all('a', text='Market Results PDF')

    # # to replace from raw
    # report = [{'href': '/{}'.format(p.name)} for p in Path('long_prairie_scrape/pdf').glob('*.pdf')]
    # report.pop(0)

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        request = Request(
            this_report['href'],
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
            line = [this_line.strip() for this_line in io.readlines()]
        temp_raw.clean()
        line = [this_line for this_line in line if this_line]
        line = [re.split(r'(?<!\$)\s{2,}|(?<=\d)\s+', this_line) for this_line in line]

        sale_date = get_sale_date(line.pop(0))
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
