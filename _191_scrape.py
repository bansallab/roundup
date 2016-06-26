import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
from os import system
import scrape_util
 
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = ['/ArchivedMarketReports.html', '/Past-Year-Archived-Market-Reports.html']
temp_raw = scrape_util.ReportRaw(argv, prefix)
strip_char = ';,.* \n\t'


def get_sale_head(line):
    """Return the total number of head sold at the sale.
    If present, the number is usually at the top of the market report."""

    sale_head = None
    for this_line in line:
        match = re.search(r'([0-9,]+) *head', this_line, re.IGNORECASE)
        if match:
            sale_head = match.group(1).replace(',', '')
            break

    return sale_head


def get_sale_date(date_string):
    """Return the date of the sale."""

    sale_date = dateutil.parser.parse(date_string)

    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_sign = re.search(r'@', this_line)
    has_price = re.search(r'[0-9]+\.[0-9]{2}', this_line)
    
    return bool(has_price and has_sign)


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
    """Test whether a string contains a number."""

    if string:
        string = re.sub(r'\$|[,-/#@ ]|cwt|he?a?d?|deal', '', string, flags = re.IGNORECASE)
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
    if number_word:
        consignor_info = word[:number_word[0]]
    else:
        return {}

    sale = {}
    if len(consignor_info)>1:
        sale['consignor_city'] = consignor_info.pop().strip(strip_char).title()

    sale['consignor_name'] = ','.join(consignor_info).strip(strip_char)

    weight_price_string = word[number_word.pop()]

    if number_word:
        head_string = word[number_word.pop()].strip()
        head_match = re.search(r'([0-9,]+) ?(hd|head)', head_string, re.IGNORECASE)
        if head_match:
            sale['cattle_head'] = head_match.group(1).replace(',','')

    weight_match = re.search(r'([0-9,.]+) ?#', weight_price_string)
    if weight_match:
        sale['cattle_avg_weight'] = weight_match.group(1).replace(',','')
        price_string = weight_price_string.replace(weight_match.group(), '')
    else:
        price_string = weight_price_string

    price_match = re.search(r'([0-9,.]+)', price_string)
    if price_match:
        sale['cattle_price_cwt'] = price_match.group(1).replace(',','')
        
    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = this_line.split(',')
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
            soup = BeautifulSoup(io.read(), 'lxml')
        report = [a for a in soup.find_all('a') if re.search(r'[0-9]{,2} ?, ?[0-9]{4}', a.get_text())]

        # Locate existing CSV files
        archive = scrape_util.ArchiveFolder(argv, prefix)

        # Write a CSV file for each report not in the archive
        for this_report in report:

            sale_date = get_sale_date(this_report.get_text())
            io_name = archive.new_csv(sale_date)

            # Continue iteration if this report is already archived
            if not io_name:
                continue

            # Initialize the default sale dictionary
            this_default_sale = default_sale.copy()
            this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                })

            request = Request(
                base_url + this_report['href'],
                headers = scrape_util.url_header,
                )
            with urlopen(request) as io:
                response = io.read()

            with temp_raw.open('wb') as io:
                io.write(response)
            system(scrape_util.pdftotext.format(str(temp_raw)))

            # read sale text into line list
            temp_txt = temp_raw.with_suffix('.txt')
            with temp_txt.open('r') as io:
                original_line = list(this_line.strip() for this_line in io)
            temp_raw.clean()

            sale_head = get_sale_head(original_line)

            this_default_sale.update({
                'sale_head': sale_head,
                })

            for this_line in original_line:
                match = re.search(r'@.+?( {5,}).+?@', this_line)
                if match:
                    split_index = this_line.find(match.group(1)) + len(match.group(1))
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
