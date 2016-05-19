import csv
from urllib.request import Request, urlopen
import urllib.error
import dateutil.parser
import datetime
import re
import xlrd
from sys import argv
from bs4 import BeautifulSoup
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market-report.php'
temp_pdf = scrape_util.ReportRaw(argv, prefix, suffix='pdf')
temp_xlsx = scrape_util.ReportRaw(argv, prefix, suffix='xlsx')
strip_char = ';,. \n\t'


def get_sale_title(this_report):
    """Return the title of the livestock sale."""
    
    header_string = this_report.get_text()
    date_string, title_string = header_string.split('::')
    title_string = title_string.strip(strip_char)

    return title_string


def get_sale_date(this_report):
    """Return the date of the sale."""
    
    header_string = this_report.get_text()
    date_string, title_string = header_string.split('::')
    date_string = date_string.strip(strip_char)
    sale_date = dateutil.parser.parse(date_string)

    return sale_date
    

def is_sale(word):
    """Determine whether a given line describes a sale of cattle."""

    is_not_succinct = len(word) > 2
    has_price = re.search(r'[0-9,]+\.[0-9]{1,2}', ' '.join(word))
    return all([is_not_succinct, has_price])


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

    # Split head and cattle string if not split
    if not is_number(word[1]):
        if re.match(r',.*',word[1]):
            word.pop(1)
        else:
            try:
                head_string, cattle_string = word[1].split(maxsplit=1)
                if is_number(head_string):
                    word.pop(1)
                    word.insert(1, head_string)
                    word.insert(2, cattle_string)
                else:
                    word.insert(1, '0')
            except ValueError:
                word.insert(1, '0')

    number_word = [idx for idx, val in enumerate(word) if is_number(val)]

    if len(number_word) == 4:
        return {}

    cattle_string = word[number_word[0]+1].strip(strip_char)

    # Skip line if the line describes the sale of sheep
    sheep_clue = r'sheep|la?mb|goat|ewe|wether|((\s|-)sh$)'
    if re.search(sheep_clue, cattle_string, re.IGNORECASE):
        return {}

    name_location_string = word[0]
    name_location = name_location_string.split(',')

    if len(name_location) == 1:
        sale = {
            'consignor_name': name_location_string.strip(strip_char).title(),
            }
    elif len(name_location_string) == 33:
        sale = {
            'consignor_name': name_location_string.strip(strip_char).title(),
            }
    elif len(name_location_string) == 37:
        sale = {
            'consignor_name': name_location_string.strip(strip_char).title(),
            }
    else:
        sale = {
            'consignor_city': name_location.pop().strip(strip_char).title(),
            'consignor_name': ','.join(name_location).strip(strip_char).title(),
            }

    sale['cattle_cattle'] = cattle_string
    head_string = word[number_word.pop(0)].strip(strip_char).replace(',', '')
    try:
        if int(head_string) > 0:
            sale['cattle_head'] = head_string
    except ValueError:
        pass

    price_string = word[number_word.pop()]

    if number_word:
        weight_string = word[number_word.pop()].strip(strip_char).replace(',', '')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass
        key = 'cattle_price_cwt'
    else:
        key = 'cattle_price'

    match = re.search(r'([0-9,.]+)', price_string, re.IGNORECASE)
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)
        
    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        word = re.split(r'\s{2,}|\t', this_line.strip())
        if is_sale(word):
            sale = this_default_sale.copy()
            sale.update(get_sale(word))
            if sale != this_default_sale:
                writer.writerow(sale)


def main():            
    
    # Collect individual reports into a list
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    content = soup.find('div', id = 'main_content')
    report = content.find_all('li')

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:
    
        sale_date = get_sale_date(this_report)

        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            continue

        if sale_date.date() <= datetime.date(2014,1,13):
            break

        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        sale_title = get_sale_title(this_report)
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_title': sale_title,
            })

        report_url = base_url + this_report.find('a')['href']
        request = Request(
            report_url,
            headers = scrape_util.url_header,
        )
        try:
            with urlopen(request) as io:
                response = io.read()
        except urllib.error.HTTPError:
            continue

        if re.search(r'\.pdf$', report_url, re.IGNORECASE):
            temp_raw = temp_pdf
            with temp_raw.open('wb') as io:
                io.write(response)
            system(scrape_util.pdftotext.format(str(temp_raw)))
            temp_txt = temp_raw.with_suffix('.txt')
            with temp_txt.open('r') as io:
                text = io.read()
            temp_raw.clean()
        elif re.search(r'\.xlsx$', report_url, re.IGNORECASE):
            temp_raw = temp_xlsx
            with temp_raw.open('wb') as io:
                io.write(response)
            temp_txt = temp_raw.with_suffix('.txt')
            with temp_txt.open('w', encoding='utf-8') as io:
                wr = csv.writer(io, lineterminator='\n\n', delimiter='\t')
                sheet = xlrd.open_workbook(str(temp_raw)).sheet_by_index(0)
                for i in range(0, sheet.nrows):
                    wr.writerow(sheet.row_values(i))
            with temp_txt.open('r') as io:
                text = io.read()
            temp_raw.clean()
        elif re.search(r'\.txt$', report_url, re.IGNORECASE):            
            text = response.decode()
        else:
            continue
            
        text_line = re.split(r'\n\n|\n\x0c|\r\n', text.strip())
        # ## the following was an erroneous attempt to deal with PDFs where the price column was on subsequent pages
        # cut = len(text_line) // 2
        # if next((False for line in text_line[cut:] if re.match(r'\$[\d\.]+', line)), True):
        #     price = text_line[cut:]
        #     text_line = text_line[:cut]
        #     for idx, val in enumerate(price):
        #         text_line[idx] += '  {}'.format(val)
        line = [this_line.replace('\n', '') for this_line in text_line]

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
