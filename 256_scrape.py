import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import json
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'events.json.php'
strip_char = ';,. \n\t'


def get_sale_date(string):
    """Return the date of the livestock sale."""

    match = re.search(r'\w*[ \d]+,[ \d]+$', string, re.IGNORECASE)
    if match:
        sale_date = dateutil.parser.parse(match.group(0)).date()
    else:
        sale_date = None
    return sale_date
    

def get_sale_head(soup):
    """Return the head of the livestock sale."""

    head = None
    head_string = soup.find('h3')
    if head_string:
        head_string = head_string.get_text()
        head_match = re.match('([0-9,]+) ?head', head_string, re.IGNORECASE)
        if head_match:
            head = head_match.group(1).replace(',','')

    return head


def is_sale(line):
    """Determine whether a given line describes a sale of cattle."""

    td = line.find_all('td')
    is_not_succinct = len(td) > 3
    has_price = False
    for this_td in td:
        if re.search(r'[0-9]+\.[0-9]{2}', this_td.get_text()):
            has_price = True
            break

    return is_not_succinct and has_price


def get_sale_location(sale_location):
    """Convert address strings into a list of address components."""

    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def is_number(string):
    """Test whether a string is numeric. Ignoring units like '$', 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale(word):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    number_word = [idx for idx, val in enumerate(word) if is_number(val)]

    if len(number_word) < 2:
        return {}

    sale_location = get_sale_location(word[number_word[0]-1])

    sale = {
        'consignor_name': word[0].strip(strip_char).title(),
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_cattle': word[-1].strip(strip_char)
    }

    if sale_location:
        sale['consignor_state'] = sale_location.pop()

    head_string = word[number_word[0]].strip(strip_char).replace(',', '')
    try:
        int(head_string)
        sale['cattle_head'] = head_string
    except ValueError:
        pass

    if len(number_word) == 2:
        price_idx = 1
    else:
        price_idx = 2      
        weight_string = word[number_word[1]].strip(strip_char).replace(',', '').replace('$','')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass

    price_string = word[number_word[price_idx]]
    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)

    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            word = [td.get_text().strip() for td in this_line.find_all('td')]
            sale = this_default_sale.copy()
            sale.update(get_sale(word))
            if sale != this_default_sale:
                writer.writerow(sale)


def main():
    
    # Get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    
    with urlopen(request) as io:
        string = io.read().decode('utf-8')

    data = json.loads(string)
    header = []
    url = []

    for item in data['result']:
        if '/past-sale/' in item['url']:
            header.append(item['title'])
            url.append(item['url'])

    report = [[h, t] for h,t in zip(header, url)]

    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    for this_report in report:

        sale_date = get_sale_date(this_report[0])
        if not sale_date:
            continue

        io_name = archive.new_csv(sale_date)        
        if not io_name:
            continue

        request = Request(
            base_url + this_report[1],
            headers = scrape_util.url_header,
            )

        with urlopen(request) as io:
            soup = BeautifulSoup(io.read(), 'lxml')

        # Initialize the default sale dictionary
        sale_head = get_sale_head(soup)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        line = []

        table = soup.find('table')
        
        for tr in table.find_all('tr'):
            line.append(tr)
        
        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)

            
if __name__ == '__main__':
    main()
