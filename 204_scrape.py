import csv
from urllib.request import Request, urlopen
from pathlib import Path
from datetime import date
import re
from sys import argv
from bs4 import BeautifulSoup
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
temp_raw = scrape_util.ReportRaw(argv, prefix)
strip_char = ';,. \n\t'


def get_sale_date(report):
    """Return the date of the livestock sale."""
    
    href = Path(report['href'])
    date_list = [int(s) for s in href.stem.split('-')]
    sale_date = date(date_list[2], date_list[0], date_list[1])
    if sale_date > date.today():
        sale_date = None
    
    return sale_date
    

def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""
    
    sale = False
    while True:
        has_price = re.search(r'\$[,0-9]+\.[0-9]{2}', this_line)
        if not has_price:
            break
        has_another_price = re.search(r'\$[,0-9]+\.[0-9]{2}\s*-\s*\$?\d+\.\d{2}', this_line)
        if has_another_price:
            break
        is_succinct = len(this_line.split()) < 6
        if is_succinct:
            break
        is_summary = re.match('(Top|Overall).*?-\s*\$', this_line)
        if is_summary:
            break
        sale = True
        break
    
    return sale


def get_sale_location(word):
    """Convert address strings into a list of address components."""
                
    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        sale_location = ['', sale_location]
    
    match = re.search(r'(.*?)(' + scrape_util.state + ')', sale_location[-1])    
    if match:
        sale_location[1:] = [
            re.sub(r'consignment( from)?', '', match.group(1), flags = re.IGNORECASE),
            match.group(2),
            ]
    else:
        sale_location.append('')
        
    return sale_location


def is_number(string):

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
    
    number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))
    if number_word[0] in [0,1]:
        number_word = number_word[1:]
        
    location_index = number_word[0]
    price_index = number_word[-1]
    cattle_begin = number_word[0] + 1
    if len(number_word) > 2:
        weight_index = number_word[len(number_word) - 2]
        weight_string = word[weight_index]
        weight_string = ''.join(weight_string.split(','))
        cattle_end = weight_index
    else:
        weight_string = ''
        cattle_end = price_index
    try:
        float(weight_string)
    except ValueError:
        weight_string = ''
        pass
    
    sale_location = get_sale_location(word[:location_index])
    sale = {
        'consignor_name': sale_location.pop(0).strip(strip_char).title(),
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'consignor_state':sale_location.pop(0).strip(strip_char),
        'cattle_avg_weight': weight_string,
        'cattle_cattle':' '.join(word[cattle_begin:cattle_end]).strip(strip_char),
        }
                
    cattle_head_string = word[location_index]
    try:
        float(cattle_head_string)
        sale.update({'cattle_head': cattle_head_string})
    except ValueError:
        pass
    
    price_string = word[price_index]
    if 'PAIR' in sale['cattle_cattle']: 
        key = 'cattle_price' 
    else: 
        key = 'cattle_price_cwt' 
    sale[key] = price_string.replace(',','').strip('$') 
        
    sale = {k:v.strip() for k,v in sale.items() if v.strip()}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if  is_sale(this_line):
            sale = this_default_sale.copy()
            word = list(filter(bool, this_line.split()))
            sale.update(get_sale(word))
            writer.writerow(sale)


def main():
    
    # Get URLs for all reports
    request = Request(
        base_url + '/sale-reports',
        headers = scrape_util.url_header,
        )
    
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'html.parser')
    
    href_pattern = re.compile('/(wp-content|belle-root)/uploads/')
    report = soup.find_all('a', href=href_pattern)

    # Bring in location of archives
    archive = scrape_util.ArchiveFolder(argv, prefix)
                
    for this_report in report:
        
        # Skip if report exists in archive
        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue
        
        # Initialize this_default_sale
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })
        
        # Request the report PDF
        if 'http' in this_report['href']:
            full_url = this_report['href']
        else:
            full_url = base_url + this_report['href']
        request = Request(
            full_url,
            headers=scrape_util.url_header,
            )
        try:
            with urlopen(request) as io:
                response = io.read()
        except:
            continue
                
        # Convert PDF to TXT file and import
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = list(this_line.strip() for this_line in io if is_sale(this_line))
        temp_raw.clean()
            
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)
    

if __name__ == '__main__':
    main()
