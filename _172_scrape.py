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
head_pattern = re.compile(r'(\d+)\s*head?', re.IGNORECASE)
sale_patterns = [
    re.compile(
        r'(^|\s{2,})(?P<head>\d+)'
        r'(?P<cattle>[^\d#]+)'
        r'#?(?P<weight>\d+)\s*@'
        r'[\s\$]+(?P<price>[0-9]+\.[0-9]{2}$)'
        ),
    re.compile(
        r'(Feeder Cattle )?-\s*(?P<head>\d+)'
        r'(?P<cattle>[^\d]+)'
        r'(?P<weight>\d+)\s+@'
        r'[\s\$]+(?P<price>[0-9]+\.[0-9]{2}$)'
        ),
    ]
location_pattern = re.compile(
    r'(^|\s{2,})(?P<city>[\w\s]+),\s*'
    r'(?P<state>' + scrape_util.state + r')$'
    )


def get_sale_date(this_report):

    date_string = this_report.get_text()
    date_string = date_string.split()[0]
    sale_date = dateutil.parser.parse(date_string, fuzzy = True)
        
    return sale_date


def get_sale_head(line):

    match = None
    while not match:
        this_line = line.pop(0)
        match = head_pattern.search(this_line)

    return match.group(1)


def get_sale_location(match):
    """Convert address strings into a list of address components."""

    sale = {
        'consignor_city': match.group('city').strip(),
        'consignor_state': match.group('state'),
        }
    
    return sale


def get_sale(match):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    sale = {
        'cattle_head': match.group('head'),
        'cattle_cattle': match.group('cattle').strip(),
        'cattle_avg_weight': match.group('weight'),
        'cattle_price_cwt': match.group('price').replace(',', ''),
        }

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        for sale_pattern in sale_patterns:
            sale_match = sale_pattern.search(this_line)
            if sale_match:
                break
        if sale_match:
            sale = this_default_sale.copy()
            sale.update(get_sale(sale_match))
        else:
            location_match = location_pattern.search(this_line)
            if location_match:
                sale.update(get_sale_location(location_match))
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
            line = [this_line.strip() for this_line in io.readlines()]
        temp_raw.clean()
        
        sale_head = get_sale_head(line)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        with io_name.open('w') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
