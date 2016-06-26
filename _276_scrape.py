import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util

 
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'topsellers.html'
strip_char = ';,. \n\t'
cattle_clue = r'(bulls?|steers?|strs?|cows?|heifers?|hfrs?|calf|calves|pairs?|head)'


def get_sale_date(title):
    """Return the date of the livestock sale."""
    #for i in number[:6]:

#    date_string = title[number[0]] + title[number[1]]
    match = re.search(r'[0-9/\-]+', title)
    date_string = match.group(0)
    sale_date = dateutil.parser.parse(date_string, fuzzy=True)
    return sale_date


def get_sale_head(title):

    match = re.search(r'([0-9,]+) *he?a?d', title, re.IGNORECASE)
    sale_head = match.group(1).replace(',','')

    return sale_head


def get_sale_location(string):

    if ',' in string:
        info = string.split(',')
    elif 'of' in string:
        info = string.split('of')
    else:
        info = [string]

    return info


def get_sale(line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    if len([this_line for this_line in line if this_line])<2:
        return {}

    consignor_location = get_sale_location(line[1])
    sale = {
        'consignor_name': consignor_location.pop(0).strip(),
        'cattle_cattle': line[0].strip(),
        }
    if consignor_location:
        sale['consignor_city'] = consignor_location.pop().strip()

    if len(line)==3:
        buyer_match = re.search(r'(.*?)(range|for)(.*)', line[2], re.IGNORECASE)
        if buyer_match:
            buyer_location = get_sale_location(buyer_match.group(1))
            sale['buyer_name'] = buyer_location.pop(0).strip()
            if buyer_location:
                sale['buyer_city'] = buyer_location.pop().strip()

            match = False
            price_string = buyer_match.group(3)
            if not match:
                match = re.search(r'\$?([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
                key = 'cattle_price'
            if not match:
                match = re.search(r'\$?([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
                key = 'cattle_price_cwt'
            if match:
                sale[key] = re.sub(r'[^0-9.]', '', match.group(1))

    sale = {k:v for k,v in sale.items() if v}
    
    return sale
 

def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        sale = this_default_sale.copy()
        sale.update(get_sale(this_line))
        if sale!=this_default_sale:
            writer.writerow(sale)


def main():            
    
    # Get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = [soup.find_all('table')[2]]

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        soup = BeautifulSoup(re.sub(r'</?br/?>', '\n', str(this_report.td)), 'lxml')
        text = re.sub(r'\xa0+', ' ', soup.get_text())
        match = re.search(r'(.+?[0-9]+\s*Head)(.*)', text, flags=re.IGNORECASE|re.DOTALL)
        title = match.group(1)
        content = match.group(2)

        sale_date = get_sale_date(title)
        io_name = archive.new_csv(sale_date)
        # Stop iteration if this report is already archived
        if not io_name:
            break
        
        # Initialize the default sale dictionary
        sale_head = get_sale_head(title)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        split = content.splitlines()

        line = []
        for this_split in split:
            match = re.search(r'(.*?)\sSold by:?\s*(.*)', this_split, re.IGNORECASE)
            if match:
                line.append([match.group(1), match.group(2)])
                continue
            match = re.search(r'bought\s+by:?\s*(.*)', this_split, re.IGNORECASE)
            if match:
                last_line = line.pop()
                last_line.append(match.group(1))
                line.append(last_line)

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
