import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '?p=market'
strip_char = ';,. \n\t'


def get_sale_title(header):
    """Return the title of the livestock sale."""
    
    header_string = header.string
    try:
        title_string, head_string, date_string = header_string.split(' - ')
    except ValueError:
        title_string, date_string = header_string.split(' - ')

    return title_string


def get_sale_head(header):
    """Return the total number of head sold at the sale.
    If present, the number is usually at the top of the market report."""
    
    header_string = header.string
    try:
        title_string, head_string, date_string = header_string.split(' - ')
        if is_number(head_string):
            head_string = head_string.replace(',', '').replace('hd', '').strip(strip_char)
            head = int(head_string)
    except ValueError:
        head = None

    return head


def get_sale_date(header):
    """Return the date of the sale."""
    
    header_string = header.string
    try:
        title_string, count_string, date_string = header_string.split(' - ')
    except ValueError:
        title_string, date_string = header_string.split(' - ')
    sale_date = dateutil.parser.parse(date_string)

    return sale_date


def is_heading(this_line):
    """Determine whether a given line is a section header 
    that describes subsequent lines of a report.
    """

    return this_line['class'] == ['newcategory']
    

def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    td = this_line.find_all('td')
    is_not_succinct = len(td) > 3
    has_price = False
    for td in td:
        if td.string:
            if re.search(r'[0-9]+\.[0-9]{2}', td.string):
                has_price = True
                break
    
    return bool(has_price and is_not_succinct)


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


def get_sale(word):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    
    number_word = [idx for idx, val in enumerate(word) if is_number(val)]
    
    sale_location = get_sale_location(word[1:2])
    sale = {
        'consignor_name': word[0].title(),
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_cattle': word[3]
        }
                
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    head_string = word[number_word[0]].strip(strip_char).replace(',', '')
    try:
        float(head_string)
        sale['cattle_head'] = head_string
    except ValueError:
        pass
    
    weight_string = word[number_word[1]].strip(strip_char).replace(',', '')
    try:
        float(weight_string)
        sale['cattle_avg_weight'] = weight_string
    except ValueError:
        pass
        
    price_string = word[number_word[2]]
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
        if is_heading(this_line):
            pass
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            word = []
            for td in this_line.find_all('td'):
                if td.string:
                    word.append(td.string)
                else:
                    word.append('')
            sale.update(get_sale(word))
            writer.writerow(sale)


def main():            
    
    # Collect individual reports into a list
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    content = soup.find('div', id='content')
    outer_table = content.find('table')
    header = outer_table.find_all('h1')
    table = outer_table.find_all('table')
    report = [[h, t] for h,t in zip(header, table)]

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:
    
        sale_date = get_sale_date(this_report[0])
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            continue
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        sale_title = get_sale_title(this_report[0])
        sale_head = get_sale_head(this_report[0])
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_title': sale_title,
            'sale_head': sale_head,
            })

        # List each line of the report
        line = this_report[1].find_all('tr')

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
