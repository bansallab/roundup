import csv
import requests
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util

 
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/category/market-information/'
strip_char = ':;,. \n\t'


def get_sale_head(line):
    """Return the total number of head sold at the sale.
    If present, the number is usually at the top of the market report."""
    
    head_string = line[1].get_text().replace('\n', ' ')
    match = re.search(r'([0-9,]+)', head_string)
    if match:
        head = match.group(1).replace(',','')
    else:
        head = None

    return head


def get_sale_date(line):
    """Return the date of the sale."""
    
    date_string = line[0].get_text().replace('\n', ' ')
    sale_date = dateutil.parser.parse(date_string, fuzzy=True)

    return sale_date


def is_heading(this_line):
    """Determine whether a given line is a section header 
    that describes subsequent lines of a report.
    """

    is_succinct = len(this_line.find_all('td')) < 3
    string = this_line.get_text()
    is_short = len(string.split()) < 10
    cattle_clue = r'bulls?|steers?|strs?|cows?|heifers?|hfrs?|calf|calves|pairs?|yearlings?'
    has_cattle = re.search(cattle_clue, string, re.IGNORECASE)

    return bool(is_succinct and is_short and has_cattle)
    

def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    td = this_line.find_all('td')
    is_not_succinct = sum(1 for this_td in td if this_td.string) > 3
    has_price = False
    has_range = False
    no_test = False
    for td in td:
        if re.search(r'[0-9]+\.[0-9]{2}', td.get_text()):
            has_price = True
        if re.search(r'\bto\b', td.get_text(), re.IGNORECASE):
            has_range = True
            break
        if re.search('no test', td.get_text(), re.IGNORECASE):
            no_test = True
            break
    
    return has_price and is_not_succinct and not has_range and not bool(no_test)


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


def get_sale(word, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    
    number_word = [idx for idx, val in enumerate(word) if is_number(val)]
    
    sale_location = get_sale_location(word[:number_word[0]])
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        }
                
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    cattle_string = cattle + ' ' + ' '.join(word[number_word[0]+1:number_word[1]])
    sale['cattle_cattle'] = cattle_string.strip(strip_char)

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
    
    cattle = ''
    for this_line in line:
        if is_heading(this_line):
            cattle = this_line.get_text().strip(strip_char)
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            word = [td.get_text().replace('\xa0','') for td in this_line.find_all('td') if td.get_text() != '']
            sale.update(get_sale(word, cattle))
            writer.writerow(sale)


def main():            
    
    # Collect individual reports into a list
    response = requests.get(
        base_url + report_path,
        headers=scrape_util.url_header,
        )
    soup = BeautifulSoup(response.text)
    report = [soup]

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        table = soup.find('table')
        line = [tr for tr in table.find_all('tr')]

        if line[0].get_text().strip():   
            sale_date = get_sale_date(line)
        else:
            date_string = soup.time.get_text()
            sale_date = dateutil.parser.parse(date_string)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            continue
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        sale_head = get_sale_head(line)
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
