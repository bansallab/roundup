import csv
import regex as re
from urllib.request import Request, urlopen
from datetime import date, datetime
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup
import scrape_util
from os import system


default_sale, base_url, prefix = scrape_util.get_market(argv)
doc_query = 'index.cfm?show=82&mid=34&viewDoc={}'
temp_raw = scrape_util.ReportRaw(argv, prefix)
sale_pattern = [
    re.compile(
        r'(?P<name>.*?)'
        r'(?P<location>\s{2,}(\w+\s)*\w+,.*?(\s{2,}|\s(?=[0-9])))'
        r'(?P<head>[0-9]*)'
        r'(?P<cattle>[^\$]+)'
        r'(?P<price>\$[0-9,\.]+)',
        ),
    re.compile(
        r'(?P<name>)'
        r'(?P<location>.*?(CONSIGNOR|CONSIGNMENT)[^0-9]*)'
        r'(?P<head>[0-9]*)'
        r'(?P<cattle>[^\$]+)'
        r'(?P<price>\$[0-9,\.]+)',
        ),
    re.compile(
        r'(?P<name>.*?)'
        r'(?P<location>,?\s*(' + scrape_util.state + r'))\s*'
        r'(?P<head>[0-9]+)' # '(?P<head>[0-9]+)'
        r'(?P<cattle>[^\$]+)'
        r'(?P<price>\$[0-9,\.]+)',
        re.IGNORECASE,
        ),
    re.compile(
        r'(?P<name>.*?)'
        r'(?P<location>)(\s{2,}|\s(?=[0-9]+\s))'
        r'(?P<head>[0-9]+)'
        r'(?P<cattle>[^\$]*\p{L}[^\$]*)'
        r'(?P<price>\$[0-9,\.]+)',
        ),
    re.compile(
        r'(?P<name>.*?)'
        r'(?P<location>)'
        r'(?P<head>)\s{2,}'
        r'(?P<cattle>[^\$]*\p{L}[^\$]*)'
        r'(?P<price>\$[0-9,\.]+)',
        ),
    ]


def get_sale_date(report):
    """Return the date of the livestock sale."""
    if isinstance(report, list):
        date_string = report[-1]
        try:
            sale_date = dateutil.parser.parse(date_string).date()
        except:
            if 'Novembers' in date_string:
                sale_date = dateutil.parser.parse(date_string.replace('Novembers', 'November')).date()
    else:
        date_string = report[-10:-4]
        sale_date = datetime.strptime(date_string, '%m%d%y').date()
    return sale_date


def get_sale_document(report):

    if isinstance(report, list):
        url = doc_query.format(report[0])
    else:
        url = report

    # Request the report PDF
    request = Request(
        base_url + url,
        headers = scrape_util.url_header
        )
    with urlopen(request) as io:
        file_type = io.getheader('content-disposition')
        if file_type and '.csv' in file_type.lower():
            return []
        else:
            response = io.read()

    # Convert PDF to TXT file and import
    with temp_raw.open('wb') as io:
        io.write(response)
    system(scrape_util.pdftotext.format(str(temp_raw)))
    temp_txt = temp_raw.with_suffix('.txt')
    with temp_txt.open('r') as io:
        line = list(this_line.strip() for this_line in io if this_line.strip())
    temp_raw.clean()

    if 'ABCD' in line[0].replace(' ', ''):
        line = [re.sub(r'^[0-9\s]+', '', this_line) for this_line in line]

    return line


def get_sale_head(line):
    """Return the total receipts for livestock for this sale."""
    head = None
    for this_line in line:
        match = re.search(r'([0-9]+)( plus)?\s*(cattle|head)', this_line, re.IGNORECASE)
        if match:
            head = match.group(1)
            break
    return head


def is_sale(line):
    has_price = bool(re.search(r'\$[0-9,]+\.[0-9]{2}', line))
    is_long = len(line) > 30
    is_average = bool(re.match(r'(average|top)\s', line, re.IGNORECASE)) 
    return has_price and is_long and not is_average


def is_heading(line):
    is_short = len(line) < 20
    has_heading = re.match('feeder|pair|bred|weigh|cow|calve', line, re.IGNORECASE)
    return is_short and bool(has_heading)


def get_sale_location(location):
    if ',' in location:
        sale_location = location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', location, re.IGNORECASE)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [location, '']

    return sale_location


def get_sale(line, heading):

    match = None
    for i, p in enumerate(sale_pattern):
        match = p.search(line)
        if match:
            # print('{}: {}'.format(i, line))
            break
    if not match:
        print('NO MATCH: {}'.format(line))
        return {}

    sale = {
        'consignor_name': match.group('name'),
        'cattle_head': match.group('head'),
        'cattle_cattle': heading + ' ',
        }
    sale_location = get_sale_location(match.group('location'))
    sale.update({
        'consignor_city': sale_location[0].title(),
        'consignor_state': sale_location[1].upper(),
        })

    weight_match = re.search(r'[0-9,]+$', match.group('cattle').strip())
    if weight_match:
        sale['cattle_avg_weight'] = weight_match.group(0).replace(',', '')
        sale['cattle_cattle'] += match.group('cattle').replace(weight_match.group(0), '').strip()
    else:
        sale['cattle_cattle'] += match.group('cattle').strip()

    if re.search(r'pair|bred', heading, re.IGNORECASE):
        price_type = 'cattle_price'
    else:
        price_type = 'cattle_price_cwt'
    sale[price_type] = re.sub(r'[^0-9\.]', '', match.group('price'))

    sale = {k: re.sub(r'\s+', ' ', v.strip()) for k, v in sale.items() if v.strip()}

    return sale


def write_sale(line, default_sale, writer):

    while 'Seller Name' not in line.pop(0):
        pass
    heading = ''
    for this_line in line:
        if is_heading(this_line):
            heading = this_line.strip()
        elif is_sale(this_line):
            sale = default_sale.copy()
            sale.update(get_sale(this_line, heading))
            if sale!=default_sale:
                writer.writerow(sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # get links for pages of current and prior reports
    request = Request(
        base_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    td = soup.find(id='nav')
    nav_string = td.find(text='Market Reports')
    current_url = nav_string.parent['href']
    nav_string = td.find(text='Cattle Market Reports')
    prior_url = nav_string.parent['href']

    # get report links from page of current reports
    request = Request(
        base_url + current_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    file_re = re.compile(r'/images/[^/]+/C[0-9]{6}\.pdf')
    report = file_re.findall(str(soup))

    # get report links from page of prior reports
    request = Request(
        base_url + prior_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    report += [[a['id'], a.string] for a in soup.find_all('a', attrs={'href': "#"})]

    for this_report in report:

        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)

        # skip iteration if this report is already archived
        if not io_name:
            continue

        line = get_sale_document(this_report)
        if not line:
            continue

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
