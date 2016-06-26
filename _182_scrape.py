import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
import dateutil.parser
from os import system
from pathlib import  PurePosixPath
import scrape_util

default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path_1 = 'sale_results.asp'
report_path_2 = 'sale%20results/'
strip_char = ';,. \n\t'
temp_raw = scrape_util.ReportRaw(argv, prefix)
    

def get_sale_date(this_report):
    match = re.search(r'(.+?)([0-9]+)_([0-9]+)', this_report)
    date_string = ' '.join([match.group(i) for i in range(1, 4)])
    sale_date = dateutil.parser.parse(date_string, fuzzy=True)
    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""
    has_price = re.search(r'[0-9]+\.[0-9]{2}', this_line)
    is_not_succinct = len(re.split(r'\s{2,}', this_line)) > 3
    
    return bool(has_price and is_not_succinct)


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/#]|cw?t?|he?a?d?', '', string, flags = re.IGNORECASE)
        try:
            float(string)
            result = True
        except ValueError:
            result = False
    else:
        result = False

    return result


def get_sale_head(line):

    sale_head = ''
    for this_line in line:
        match = re.search(r'head *sold ?: *([0-9,]+)', this_line, re.IGNORECASE)
        if match:
            sale_head = match.group(1).replace(',','')
            break
        if not match:
            match = re.search(r'([0-9,]+) *head', this_line, re.IGNORECASE)
            if match:
                sale_head = match.group(1).replace(',','')
                break
        
    return sale_head


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


def get_sale(word):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    number_word = [idx for idx, val in enumerate(word) if is_number(val)]

    name_location = ' '.join(word[0:number_word[0]])
    location_match = re.search(r'\[(.*)\]', name_location,re.IGNORECASE)
    if location_match:
        sale_location = [location_match.group(1).strip()]
        consignor_name = name_location.replace(location_match.group(),'')
        sale_location = get_sale_location(sale_location)
    else:
        location_incomplete_match = re.search(r'\[(.*)', name_location,re.IGNORECASE)
        if location_incomplete_match:
            consignor_name = name_location.replace(location_incomplete_match.group(),'')
            if re.search(scrape_util.state + r'$', location_incomplete_match.group(1)):
                sale_location = [location_incomplete_match.group(1).strip()]
                sale_location = get_sale_location(sale_location)
            else:
                sale_location = []
        else:
            consignor_name = name_location
            sale_location = []

    sale = {
        'consignor_name': consignor_name.strip(strip_char).title(),
        'cattle_cattle': ' '.join(word[number_word[0]+1:number_word[1]])
        }

    if sale_location:
        sale['consignor_city'] = sale_location.pop(0).strip(strip_char).title()
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)
    
    head_string = word[number_word[0]].strip(strip_char).replace(',','')
    try:
        int(head_string)
        sale['cattle_head'] = head_string
    except ValueError:
        pass

    weight_string = word[number_word[1]].strip(strip_char).replace(',','').replace('#','')
    try:
        float(weight_string)
        sale['cattle_avg_weight'] = weight_string
    except ValueError:
        pass

    price_string = ''.join(word[number_word[2]:])
    
    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)
        
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    for idx, this_line in enumerate(line):
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = re.split(r'\s{2,}|(?<=\d)\s', this_line)
            sale.update(get_sale(word))
            writer.writerow(sale)


def main():
    
    # get URLs for all reports
    request = Request(
        base_url + report_path_1,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    content = soup.findAll('table')
    report = content[1].findAll('a')
    
    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:
        this_report = this_report['href']
        if 'consignments/' in this_report:
            continue
        this_report_stem = PurePosixPath(this_report).stem
        sale_date = get_sale_date(this_report_stem)

        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        this_report = this_report_stem + '.pdf'
        request = Request(
            base_url + report_path_2 + this_report,
            headers = scrape_util.url_header,
            )
        
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # create temporary text file from downloaded pdf
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))
        
        # read sale text into line list
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = [this_line.strip().replace('\xa0', ' ') for this_line in io]
        temp_raw.clean()

        sale_head = get_sale_head(line)
        this_default_sale['sale_head'] = sale_head
                    
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
