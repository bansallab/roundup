import csv
from urllib.request import Request, urlopen
from datetime import date
import re
from sys import argv
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/market_cards/scan.PDF'
temp_raw = scrape_util.ReportRaw(argv, prefix)
#CONVERT_SPEC = '-density 600 {!s} -crop 2400x4000+100+1800 -threshold 20% -deskew 40% -morphology close disk:3 -threshold 30%'
#CONVERT_SPEC = '-density 600 {!s} -crop 2400x4000+100+1800 -threshold 50% -deskew 40% -morphology close disk:3 -threshold 30%'
CONVERT_SPEC = '-density 600 {!s} -crop 2400x4400+100+1200 -threshold 50% -deskew 40% -morphology close disk:3 -threshold 30%'
sale_pattern = [
    re.compile(
        r'(?P<city>.*?)[\.,\s]+'
        r'(?P<state>' + scrape_util.state + ')'
        r'(?P<cattle>[^0-9]+)'
        r'(?P<weight>[0-9]+)[^\$]*'
        r'\$(?P<price>[0-9,\.]+)(?P<hd>/hd)?',
        re.IGNORECASE,
        ),
    re.compile(
        r'(?P<city>.*?)[\.,\s]+'
        r'(?P<state>' + scrape_util.state + ')'
        r'(?P<cattle>[^0-9]+)'
        r'([^\$]+)'
        r'\$(?P<price>[0-9,\.]+)(?P<hd>/hd)?',
        re.IGNORECASE,
        ),
    re.compile(
        r'(?P<city>.*?)[\.,]'
        r'(?P<cattle>.*?)'
        r'(?P<weight>\d+)#[^\$]*'
        r'\$(?P<price>[0-9,\.]+)(?P<hd>/hd)?',
        re.IGNORECASE,
        ),
    ]


def get_sale_date(line):

    date_pattern = re.compile(r'([0-9]{1,2})[/I1l]([0-9]{1,2})[/I1l]([0-9]{2})')
    match = False
    while not match and line:
        this_line = line.pop(0)
        match = date_pattern.search(this_line)
    if match:
        line.insert(0, this_line)
        date_list = [int(match.group(idx)) for idx in [3, 1, 2]]
        date_list[0] += 2000
        sale_date = date(*date_list)
    else:
        sale_date = None

    return sale_date


def get_sale_head(line):
    """Return the date of the livestock sale."""

    head_pattern = re.compile(r'receipts.*?\b(?P<date>[0-9]+)\s*hd', re.IGNORECASE)
    match = False
    while not match:
        this_line = line.pop(0)
        match = head_pattern.search(this_line)
    sale_head = match.group('date')

    return sale_head


def is_heading(line):

    line = line.replace(' ', '')
    cattle_clue = '(bulls?|steers?|cows?|heiferettes?|heifers?|calves|pairs?)'
    has_cattle = re.search(cattle_clue, line, re.IGNORECASE)

    return bool(has_cattle)


def is_sale(line):

    dollar = line.count('$')
    weight = line.count('#')
    is_not_succinct = len(line.split()) > 3
    has_range = '-' in line

    return dollar == 1 and weight == 1 and is_not_succinct and not has_range


def get_sale(line, cattle):

    line = re.sub(r'\b1X\b', 'TX', line)

    for idx, p in enumerate(sale_pattern):
        match = p.search(line)
        if match:
            break

    price_type = 'cattle_price_cwt'
    if match.group('hd'):
        price_type = 'cattle_price'
    sale = {
        'consignor_city': match.group('city').title(),
        'cattle_cattle': ' '.join([cattle, match.group('cattle').strip()]),
        price_type: match.group('price').replace(',', ''),
        }
    if idx==0:
        sale.update({
            'consignor_state': match.group('state').upper(),
            'cattle_avg_weight': match.group('weight'),
            })
    elif idx==1:
        sale.update({
            'consignor_state': match.group('state').upper(),
            })
    elif idx==2:
        sale.update({
            'cattle_avg_weight': match.group('weight'),
            })

    sale = {k: v.strip() for k, v in sale.items()}
    sale = {k: v for k, v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    cattle = ''
    for this_line in line:
        if is_heading(this_line):
            cattle = re.search(r'([^:]+)', this_line).group(0).strip()
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line, cattle))
            writer.writerow(sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    report = [None]

    # Write a CSV file for each report not in the archive
    for this_report in report:

        # Get PDF report
        request = Request(
            base_url + report_path,
            headers=scrape_util.url_header,
            )
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)

        # Convert PDF to JPG and do OCR
        temp_img = temp_raw.with_suffix('.png')
        convert = scrape_util.convert.format(CONVERT_SPEC.format(temp_raw), '', str(temp_img))
        system(convert)
        temp_txt = temp_raw.with_suffix('.txt')
        tesseract = scrape_util.tesseract.format(
            str(temp_img),
            str(temp_txt.with_suffix('')),
            prefix,
            )
        system(tesseract)
        with temp_txt.open('r') as io:
            line = io.read()
        temp_raw.clean(dirty=False)

        # Clean-up
        line = line.splitlines()

        # Stop iteration if this report is already archived
        sale_date = get_sale_date(line)
        if not sale_date:
            continue
        io_name = archive.new_csv(sale_date)
        if not io_name:
            break

        # Initialize the default sale dictionary
        sale_head = get_sale_head(line)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
