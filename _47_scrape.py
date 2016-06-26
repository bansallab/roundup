import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util

 
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'Past%20Auction%20Results.htm'
strip_char = ';,. \n\t'


def get_sale_date(header):
    """Return the date of the sale."""

    sale_date = dateutil.parser.parse(header, fuzzy=True)

    return sale_date


def get_sale_head(footer):

    match = re.search(r'([0-9,]+) *(hd|head)? *sold', footer, re.IGNORECASE)
    if match:
        head = match.group(1).replace(',','')
    else:
        head = None

    return head


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    word = [td.get_text().strip() for td in this_line.find_all('td') if td.get_text().strip() != '']
    is_not_succinct = len(word) > 2
    has_price = False
    for this_word in word:
        if re.search(r'[0-9]+\.[0-9]{2}', this_word):
            has_price = True
            break
    
    return bool(has_price and is_not_succinct)


def get_sale_location(sale_location):
    """Convert address strings into a list of address components."""

    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')$', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/@]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
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
    
    sale_location = get_sale_location(word[0])
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        }
                
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    cattle_string = word[1].strip(strip_char)
    head_match = re.match(r'([0-9,]+)', cattle_string)
    if head_match:
        sale['cattle_head'] = head_match.group(1).replace(',','')
        cattle_string = cattle_string.replace(head_match.group(),'').strip(strip_char)

    if len(word) > 3:
        cattle_string = cattle_string + ' ' + word[number_word[-1]-1].strip(strip_char)
    sale['cattle_cattle'] = cattle_string

    if '@' in word[number_word[-1]]:
        weight_string, price_string = word[number_word[-1]].split('@')
        key = 'cattle_price_cwt'
        weight_string = weight_string.strip(strip_char).replace(',','')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass
    else:
        price_string = word[number_word[-1]]
        key = 'cattle_price'

    try:
        price_string = price_string.strip(strip_char).replace('$','').replace(',','')
        float(price_string)
        sale[key] = price_string
    except ValueError:
        pass
        
    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = []
            for td in this_line.find_all('td'):
                if td.get_text().strip() != '':
                    word.append(td.get_text().replace('\xa0','').strip())
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
    content = soup.find('td', attrs={'class': 'textarea'})
    report = content.find_all('table')

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        header = None
        for sibling in this_report.previous_siblings:
            if sibling.name == 'h1':
                header = sibling.get_text()
                break
        if not header:
            for sibling in this_report.previous_siblings:
                if hasattr(sibling, 'b'):
                    header = sibling.get_text()
                    break
    
        sale_date = get_sale_date(header)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()

        for sibling in this_report.next_siblings:
            if sibling.name == 'h1':
                footer = sibling.get_text()
                break

        sale_head = get_sale_head(footer)

        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # List each line of the report
        line = this_report.find_all('tr')

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
