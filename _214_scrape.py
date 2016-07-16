import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from os import system
from sys import argv
from bs4 import BeautifulSoup
from datetime import date
import scrape_util
 

default_sale, base_url, prefix = scrape_util.get_market(argv)
default_sale = default_sale[0]
report_path = 'market-report.php'
temp_raw = scrape_util.ReportRaw(argv, prefix)
sale_pattern = [
    re.compile(
        r'(?P<name>[^,]+),'
        r'(?P<city>[^\d,]+),?\s+'
        r'(?P<head>\d+)\s*'
        r'(?P<cattle>.+?)[\s_]{2,}'
        r'(?P<weight>[\d,\.]*)\s+'
        r'\$(?P<price>[\d,\.]+)\s*'
        r'(?P<price_type>/Hd|/Cwt)?',
        re.IGNORECASE
        ),
    re.compile(
        r'(?P<name>.+?)\s{2,}'
        r'(?P<city>)'
        r'(?P<head>\d+)\s+'
        r'(?P<cattle>.+?)\s{2,}'
        r'(?P<weight>[\d,\.]*)\s+'
        r'\$(?P<price>[\d,\.]+)\s*'
        r'(?P<price_type>/Hd|/Cwt)?',
        re.IGNORECASE
        ),
    re.compile(
        r'(?P<name>[^,]+),'
        r'(?P<city>.+?)\s{2,}'
        r'(?P<head>)'
        r'(?P<cattle>.+?)\s{2,}'
        r'(?P<weight>[\d,\.]*)\s+'
        r'\$(?P<price>[\d,\.]+)\s*'
        r'(?P<price_type>/Hd|/Cwt)?',
        re.IGNORECASE
        ),
    ]
not_cattle_pattern = re.compile(r'goat|hog|ewe|buck|lamb|kid|sow|mare', re.IGNORECASE)
head_pattern = re.compile(r'([,\d]+)\s+he?a?d', re.IGNORECASE)


def get_sale_head(line):
    """Return the total number of head sold at the sale.
    If present, the number is usually at the top of the market report."""
    
    for this_line in line:
        match = head_pattern.search(this_line)
        if match:
            return match.group(1).replace(',','')


def get_sale_date(this_report):
    """Return the date of the sale."""
    
    date_string = this_report.get_text().replace('.pdf', '')
    sale_date = dateutil.parser.parse(date_string, fuzzy=True).date()
    if sale_date > date.today():
        sale_date = None

    return sale_date
    

def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    is_not_succinct = len(this_line.split()) > 3
    has_price = '$' in this_line

    return has_price and is_not_succinct


def get_sale(line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    for p in sale_pattern:
        match = p.search(line)
        if match:
            break

    if not_cattle_pattern.search(match.group('cattle')):
        return {}

    sale = {
        'consignor_name': match.group('name'),
        'consignor_city': match.group('city'),
        'cattle_head': match.group('head'),
        'cattle_cattle': match.group('cattle'),
        'cattle_avg_weight': match.group('weight').replace(',', '').replace('.', ''),
        }
    price = match.group('price').replace(',', '')
    if match.group('price_type') == '/Hd':
        sale['cattle_price'] = price
    else:
        sale['cattle_price_cwt'] = price

    sale = {k: v.strip() for k, v in sale.items() if v.strip()}
    
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
    
    # Collect individual reports into a list
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    content = soup.find('div', id = 'content')
    report = content.find_all('a')

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        if 'horse' in this_report.get_text().lower():
            continue
    
        sale_date = get_sale_date(this_report)
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

        # create temporary text file from downloaded pdf
        pdf_url = base_url + this_report['href']
        request = Request(
            pdf_url,
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))

        # read sale text into line list
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            original_line = [this_line.strip() for this_line in io.readlines() if this_line.strip()]
        if not original_line:
            temp_img = temp_raw.with_suffix('.tiff')
            system(scrape_util.convert.format("-density 400x400", str(temp_raw), str(temp_img)))
            system(scrape_util.tesseract.format("-c preserve_interword_spaces=1", str(temp_img), str(temp_txt.with_suffix(''))))
            with temp_txt.open('r') as io:
                original_line = [this_line.strip() for this_line in io.readlines() if this_line.strip()]
        temp_raw.clean()

        # # Default split index set at 120 to handle Jan 22, 2015 report with one column of sale
        # split_index = 120

        # # Look for line with two sales and the index to split the line into two columns
        # for this_line in original_line:
        #     if re.search(r'([0-9,]+\.[0-9]{2}).+?([0-9,]+\.[0-9]{2})', this_line):
        #         match = re.search(r'(/cwt|/he?a?d?)', this_line, re.IGNORECASE)
        #         if match:
        #             split_index = this_line.find(match.group(1)) + len(match.group())
        #             break

        # column1 = list(this_line[0:split_index].strip() for this_line in original_line)
        # column2 = list(this_line[split_index+1:].strip() for this_line in original_line)

        # line = column1 + column2
        line = list(filter(bool, original_line))
        if not line:
            continue

        sale_head = get_sale_head(line)
        this_default_sale['sale_head'] = sale_head

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
