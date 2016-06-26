import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/page2.html'
strip_char = ';,. \n\t'


def get_sale_date(this_report):
    """Return the date of the livestock sale."""

    report_date = this_report.find('div', id = 'txt_117')
    report_date = report_date.p.get_text()
    report_date = report_date.split('-')
    date_string = str(report_date[0])
    sale_date = dateutil.parser.parse(date_string, fuzzy = True)
    return sale_date


def get_sale_head(this_report):
    """Return the date of the livestock sale."""

    report_head = this_report.find('div', id = 'txt_117')
    report_head = report_head.p.get_text()
    report_head = report_head.split('-')
    for string in report_head:
        if re.search(r'hd|head',string,re.IGNORECASE):
            match = re.search(r'([0-9]+)',string)
            if match:
                return match.group(1)


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""
    
    has_price = re.search(r'[0-9]+\.[0-9]{2}', str(this_line))
    
    return bool(has_price)


def get_sale(this_line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    
    sale = {}
    sale['consignor_name'] = this_line.pop(0)
    sale['consignor_city'] = this_line.pop(0).title()
    try:
        maybe_head = this_line[0].split()
        int(maybe_head[0])
        sale['cattle_head'] = maybe_head[0]
        sale['cattle_cattle'] = ' '.join(maybe_head[1:])
        this_line.pop(0)
    except:
        sale['cattle_cattle'] = this_line.pop(0)
    sale['cattle_avg_weight'] = this_line.pop(0)
    price_string = this_line.pop(0)
    sale['cattle_price_cwt'] = price_string.replace(',', '')
    
    return sale
 

def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line))
            writer.writerow(sale)


def main():            
    
    # Get URLs for all reports
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
    
        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            continue
        
        # Initialize the default sale dictionary
        sale_head = get_sale_head(this_report)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # Read the report text into a list of lines
        heading = ' COWS/PAIRS/BULLS'
        table_1 = this_report.find_all('table')
        table_tr = table_1[0].find_all('tr')
        line = []
        for this_table_tr in table_tr:
            table_td = this_table_tr.find_all('td')
            table_col= [td.get_text().strip() for td in table_td]
            table_col[2] += heading
            line.append(table_col)

        heading = ' STOCKER/FEEDER'
        div_row = []
        counter = 1
        while counter:
            row_re = re.compile(r'table_1_R{:02}C0[0-5]'.format(counter))
            div_col = this_report.find_all('div', id=row_re)
            if div_col:
                div_col = [this_col.get_text().strip() for this_col in div_col]
                div_col[2] += heading
                line.append(div_col)
                counter += 1
            else:
                counter = False
        
        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
