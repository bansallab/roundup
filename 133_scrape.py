import csv
from urllib.request import Request, urlopen
import urllib.error
import dateutil.parser
import re
from os import system
from sys import argv
from bs4 import BeautifulSoup
import scrape_util
 

default_sale, base_url, prefix = scrape_util.get_market(argv)
temp_raw = scrape_util.ReportRaw(argv, prefix)
#report_path = ['/market-reports.html', '/2013-market-reports-2.html', '/2013-market-reports.html', '/2012-reports.html', '/2011-reports.html']
report_path = ['/market-reports.html', '/2013-market-reports-2.html', '/2013-market-reports.html', '/2012-reports.html']
strip_char = ';,. \n\t'


def get_sale_date(date_string):
    """Return the date of the sale."""

    date_string = date_string.replace('\xa0',' ')
    match = re.search(r'& ?[0-9]+', date_string)
    if match:
        date_string = date_string.replace(match.group(),'')
    sale_date = dateutil.parser.parse(date_string)
    # Special Case
    if sale_date.year == 201:
        sale_date = sale_date.replace(year = 2014)

    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    is_not_succinct = len(re.split(r'\.{2,}', this_line)) > 2
    has_number = re.search(r'[0-9]+', this_line)
    start_with_number = re.match(r'[0-9]+', this_line)

    return bool(has_number and is_not_succinct and not start_with_number)


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/()]|cwt|he?a?d?|pr?|avg\.?', '', string, flags = re.IGNORECASE)
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
    if len(number_word) == 0:
        return {}

    sale = {
        'consignor_name': word[0].strip(strip_char).title(),
        }

    cattle_weight_list = word[1].split(',')
    if len(cattle_weight_list) > 1:
        weight_string = cattle_weight_list.pop().strip()
        weight_string = weight_string.replace('#','').strip(strip_char)
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass
    cattle_string = ','.join(cattle_weight_list).strip()

    head_match = re.match(r'([0-9,]+)' ,cattle_string)
    if head_match:
        head_string = head_match.group(1).replace(',','').strip(strip_char)
        try:
            int(head_string)
            sale['cattle_head'] = head_string
        except ValueError:
            pass
        cattle_string = cattle_string.replace(head_match.group(1), '').strip(strip_char)

    sale['cattle_cattle'] = cattle_string

    price_string = word[number_word.pop()]
    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?(he?a?d?|pr?)', price_string, re.IGNORECASE)
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

    consignor_name = ''

    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = re.split(r'\.{2,}', this_line)

            if not re.match(r'\.{2,}', this_line):
                match = re.match(r'(.+?)\.{2,}', this_line)
                if match:
                    consignor_name = match.group(1)
            # Assign consignor name of previous row if consignor name not found
            else:
                word[0] = consignor_name

            sale.update(get_sale(word))
            if sale != this_default_sale:
                writer.writerow(sale)


def main():            

    for this_report_path in report_path:

        # Collect individual reports into a list
        request = Request(
            base_url + this_report_path,
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read())
        content = soup.find('div', itemprop = 'articleBody')
        report = content.find_all('a')

        # Locate existing CSV files
        archive = scrape_util.ArchiveFolder(argv, prefix)

        # Write a CSV file for each report not in the archive
        for this_report in report:

            sale_date = get_sale_date(this_report.get_text())
            io_name = archive.new_csv(sale_date)
            if not io_name:
                continue

            # Initialize the default sale dictionary
            this_default_sale = default_sale.copy()
            this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                })

            # create temporary text file from downloaded pdf
            pdf_url = base_url + this_report['href']
            request = Request(
                pdf_url,
                headers = scrape_util.url_header,
            )
            try:
                with urlopen(request) as io:
                    response = io.read()
            except urllib.error.HTTPError:
                continue
            with temp_raw.open('wb') as io:
                io.write(response)
            system(scrape_util.pdftotext.format(str(temp_raw)))

             # read sale text into line list
            temp_txt = temp_raw.with_suffix('.txt')
            if scrape_util.platform=='win32':
                read_errors = 'ignore'
            else:
                read_errors = None
            with temp_txt.open('r', errors=read_errors) as io:
                original_line = list(this_line.strip() for this_line in io)
            temp_raw.clean()
            split_index = 110

            # Look for line with two sales and the index to split the line into two columns
            for this_line in original_line:
                match = re.search(r'(\.{2,} *[0-9,]+).+?( {3,}).+?(\.{2,} *[0-9,]+)', this_line)
                if match:
                    split_index = this_line.find(match.group(2)) + len(match.group(2))
                    break

            column1 = list(this_line[0:split_index].strip() for this_line in original_line)
            column2 = list(this_line[split_index:].strip() for this_line in original_line)

            line = column1 + column2

            # Open a new CSV file and write each sale
            with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()
                write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
