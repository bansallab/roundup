import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
from datetime import date
import scrape_util
 

default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t'


def get_sale_date(info_list):
    """Return the date of the livestock sale."""
    
    info_list = ' '.join(info_list)
    match = re.search(r'market report(.*?)sold', info_list, re.IGNORECASE)
    sale_date = dateutil.parser.parse(match.group(1), fuzzy=False).date()

    return sale_date


def is_report(report):

    has_report = re.search("marketreport?",str(report))
    return bool(has_report)


def is_cattle(report):
    cattle_clue = '(HEIFERS?|STEERS?|COWS?|BULLS?)'
    has_cattle = re.search(cattle_clue, str(report), re.IGNORECASE)
    return bool(has_cattle)



def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    has_number = re.search("[0-9]+?",string)
    return bool(has_number)



def get_sale_head(info_list):
    """Return the total number of cattle sold, from top of market report."""
    has_sale_head = re.search("SOLD+?",str(info_list))
    return bool(has_sale_head)


def is_heading(this_line):
    """Determine whether a given line is a section header 
    that describes subsequent lines of a report.
    """
    cattle_clue = '(HEIFERS?|STEERS?|COWS?|BULLS?)'
    has_cattle = re.search(cattle_clue, str(this_line), re.IGNORECASE)
    is_succinct = (len(this_line) <= 2 and len(this_line[0])<30)
    
    return bool(has_cattle and is_succinct)


def is_category(this_line):
    category = ('WEIGHT?|PRICE?')
    has_category = re.search(category, str(this_line),re.IGNORECASE)
    is_succinct = (len(this_line) <= 6 and len(this_line[0])<6)
    return bool(has_category and is_succinct)



def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = re.search(r'\$[0-9]+?', str(this_line))
    is_not_succinct = len(this_line) > 2 and len(this_line) < 6
    
    return has_price and is_not_succinct


def is_location(this_line):
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

    return bool(has_town)


def get_sale(this_line, cattle, category):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    cattle = cattle.replace("MARKET","")
    cattle = cattle.replace(":","")
    cattle = cattle.strip().title()
    sale = {'cattle_cattle': cattle}
    if bool(re.search("TOWN", str(category))):
        for idx,title in enumerate(category):
            if title == "TOWN":
                sale['consignor_city'] = this_line[idx].strip().title()
            if title == "HEAD":
                head = this_line[idx]
                if '-' in head:
                    head = head.split('-')[0]
                if '/' in head:
                    head = head.split('/')[0]
                sale['cattle_head'] = head
            if title == "KIND":
                cattle = cattle + ' '+ this_line[idx].title()
                sale['cattle_cattle'] = cattle
            if title == "WEIGHT":
                sale['cattle_avg_weight'] = this_line[idx].replace(",","")
            if title == "PRICE":
                price = this_line[idx].replace("$","")
                price = price.replace(",","")
                if bool(re.search("Pairs", cattle)):
                    sale['cattle_price'] = price
                else:
                    sale['cattle_price_cwt'] = price
    else:
        sale={}            
    sale = {k: v.strip() for k, v in sale.items() if v}
    
    return sale


def write_sale(lines, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in lines:
        if is_heading(this_line):
            cattle = this_line[0]
        elif is_category(this_line):
            category = this_line
        elif is_sale(this_line):
            sale = get_sale(this_line, cattle,category)
            if sale:
                sale.update(this_default_sale.copy())
                writer.writerow(sale)


def main():            
    
    # Get URLs for all reports
    request = Request(
        base_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    a = soup.findAll("a")
    report = set(this_a.get('href') for this_a in a if is_report(this_a))

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:
        request = Request(
            base_url + this_report,
            headers=scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read())            
        table = soup.find_all("table")
        if is_cattle(table):
            info_list = table[0].get_text().split()
            this_report = table[1]
            sale_date = get_sale_date(info_list)
            io_name = archive.new_csv(sale_date)
        else:
            continue

        # Stop iteration if this report is already archived
        if not io_name:
            break

        # Total number of head sold
        sale_head = ''
        if get_sale_head(info_list):
            sale_head = info_list[-1].replace(",","")

        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # Read the report text into a list of lines
        line = []
        tr = this_report.find_all("tr")
        for this_tr in tr:
            td = this_tr.find_all("td")
            table_col = [td.get_text().strip() for td in td if ("\xa0" not in td and td)]
            line.append(table_col)

        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)
        

if __name__ == '__main__':
    main()
