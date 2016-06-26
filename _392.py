import csv
import requests
import dateutil.parser
import re
from os import system
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


temp_raw = scrape_util.ReportRaw(argv, prefix)
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'Market-Reports.php'
strip_char = ';,. \n\t'


def get_sale_date_and_head(line):
    """Return the total number of head sold at the sale.
    If present, the number is usually at the top of the market report."""
    
    match = False
    while not match:
        this_line = line.pop(0)
        match = re.search(r'(?P<date>.*?)head *co?u?n?t[^\d]*(?P<head>[\d,]+)', this_line, re.IGNORECASE)
    sale_date = dateutil.parser.parse(match.group('date').strip()).date()

    return sale_date, match.group('head').replace(',', '')
    

def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    is_not_succinct = len(re.split('\s{2,}',this_line)) > 3
    has_price = re.search(r'[\d,]+\.\d{2}', this_line)
    has_price_range = re.search(r'\d+-\$?\d+', this_line)

    return is_not_succinct and has_price and not has_price_range


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + r')$', sale_location)
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

    # Join price with unit of price if separated
    if not is_number(word[len(word)-1]):
        price_word = ' '.join(word[len(word)-2:])
        word.pop()
        word.pop()
        word.append(price_word)

    number_word = [idx for idx, val in enumerate(word) if is_number(val)]

    # Skip lines with four or more number words
    if len(number_word) not in [2, 3]:
        return {}

    cattle_string = ' '.join(word[number_word[0]+1:number_word[1]]).strip(strip_char)

    non_cattle_clue = r'\bbuck\b|\bewe\b|\bgelding\b|\bgoat\b|\blamb\b|\bhog\b|\bgoatpr\b|\bdonkey\b'

    # Skip lines describing sales of non-cattle
    if re.search(non_cattle_clue, cattle_string, re.IGNORECASE):
        return {}

    name_location = ' '.join(word[0:number_word[0]])
    if ',' in name_location:
        name_location_list = re.split(',', name_location)
        sale_location = get_sale_location([name_location_list[1]])
        head_string = word[number_word.pop(0)].strip(strip_char).replace(',', '')
    elif not cattle_string:
        name_location_list = ['']
        sale_location = ['','']
        head_string = ''
        cattle_string = name_location
        
    sale = {
        'consignor_name': name_location_list[0].title(),
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_cattle': cattle_string
        }
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    try:
        int(head_string)
    except ValueError:
        pass
    else:
        sale['cattle_head'] = head_string

    price_string = word[number_word.pop()]

    if number_word:
        weight_string = word[number_word.pop()].replace(',', '').strip(strip_char)
        try:
            float(weight_string)
        except ValueError:
            pass
        else:
            sale['cattle_avg_weight'] = weight_string

    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)
        
    sale = {k: v.strip() for k, v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = re.split(r'\s{2,}',this_line)
            sale.update(get_sale(word))
            if sale != this_default_sale:
                writer.writerow(sale)


def main():            
    
    response = requests.get(base_url + report_path, headers=scrape_util.url_header)
    soup = BeautifulSoup(response.content, 'lxml')
    div = soup.find_all('div', attrs={'class':'File_Default'})
    report = [this_div.a for this_div in div]
    report.reverse()

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        # create temporary text file from downloaded pdf
        pdf_url = base_url + this_report['href']
        response = requests.get(pdf_url, headers=scrape_util.url_header)
        with temp_raw.open('wb') as io:
            io.write(response.content)
        system(scrape_util.pdftotext.format(str(temp_raw)))

        # read sale text into line list
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            original_line = list(this_line for this_line in io)
        temp_raw.clean()
    
        sale_date, sale_head = get_sale_date_and_head(original_line)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # Default split index set at 120 to handle Jan 22, 2015 report with one column of sale
        split_index = 120

        # Look for line with two sales and the index to split the line into two columns
        for this_line in original_line:
            if re.search(r'([0-9,]+\.[0-9]{2}).+?([0-9,]+\.[0-9]{2})', this_line):
                match = re.search(r'(/cwt|/he?a?d?)', this_line, re.IGNORECASE)
                if match:
                    split_index = this_line.find(match.group(1)) + len(match.group())
                    break

        column1 = list(this_line[0:split_index].strip() for this_line in original_line)
        column2 = list(this_line[split_index+1:].strip() for this_line in original_line)
        line = column1 + column2

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
