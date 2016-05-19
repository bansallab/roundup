import csv
from urllib.request import Request, urlopen
import dateutil.parser
import datetime
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util

 
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'index_files/Page452.htm'
report_date_path = 'index_files/Page648.htm'
head_pattern = re.compile(r'([\d,]+) ?head', re.IGNORECASE)
strip_char = ';,. \n\t'


def get_sale_date():
    """Return the date of the sale."""
    
    request = Request(
        base_url + report_date_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')

    tables = soup.find_all('table')

    sale_date = datetime.datetime(2005, 1, 1)

    for x in range(len(tables) - 1, 0, -1):
        a = tables[x].find_all('a')
        if not a:
            continue
        else:
            new_date_string = a[-1].get_text()
            try:
                new_sale_date = dateutil.parser.parse(new_date_string)
                if new_sale_date > sale_date:
                    sale_date = new_sale_date
            except TypeError:
                pass

    return sale_date


def get_sale_head(this_report):
    """Return the head of the sale."""

    text = this_report.find(text=head_pattern)
    head_match = head_pattern.search(text)
    if head_match:
        return head_match.group(1).replace(',','')
    else:
        return None


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_number = re.search(r'[0-9]+', this_line)
    has_colon = ':' in this_line

    return bool(has_number) and has_colon


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
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
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
        try:
            float(string)
            result = True
        except ValueError:
            result = False
    else:
        result = False

    return result


def get_sale(line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    consignor_info, cattle_info = line.split(':')
    
    consignor_info_list = consignor_info.split(',')
    sale = {
        'consignor_name': consignor_info_list.pop(0),
        }
                
    if consignor_info_list:
        sale['consignor_city'] = consignor_info_list.pop().strip(strip_char)

    weight_match = re.search(r'([0-9,]+)#', cattle_info)
    if weight_match:
        sale['cattle_avg_weight'] = weight_match.group(1).replace(',','')
        cattle_info = cattle_info.replace(weight_match.group(),'')
        key = 'cattle_price_cwt'
    else:
        key = 'cattle_price'

    if re.search(r'\$', cattle_info):
        cattle_string, price_string = cattle_info.split('$')
    else:
        price_match = re.search(r'([0-9,.]+)$', cattle_info)
        if price_match:
            price_string = price_match.group(1)
            cattle_string = cattle_info.replace(price_match.group(), '')

    sale['cattle_cattle'] = cattle_string.strip(strip_char)

    try:
        float(price_string.replace(',',''))
        sale[key] = price_string.replace(',','').strip(strip_char)
    except ValueError:
        pass

    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line))
            writer.writerow(sale)


def main():            
    
    # Collect individual reports into a list
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = [soup]

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        sale_date = get_sale_date()
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break

        sale_head = get_sale_head(this_report)
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        table = this_report.find_all('table')[-1]
        # List each line of the report
        line = []
        for tr in table.find_all('tr'):
            for td in tr.find_all('td'):
                line.append(td.get_text().strip())

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
