import csv
from pathlib import Path
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
blog_url = base_url + 'site/?cat=1'


class Report(object):

    def __init__(self, link):
        request = Request(
            link['href'],
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            self.soup = BeautifulSoup(io.read())

    def __iter__(self):
        return self

    def __next__(self):
        next = self.soup.find('link', attrs={'rel': 'next'})
        if next:
            request = Request(
                next['href'],
                headers = scrape_util.url_header,
                )
            with urlopen(request) as io:
                soup = BeautifulSoup(io.read())
            self.soup = soup
            date_string = soup.find('span', {'class': 'PostHeader'}).get_text()
            report_text = soup.find_all('div', {'class': 'PostContent'})[1]
            if skip_report(report_text):
                [date_string, report_text] = self.__next__()
            return [date_string, report_text]
        else:
            raise StopIteration


def skip_report(this_report):
    has_report = re.search(r'Cattle Report+?', this_report.get_text())
    return not bool(has_report)


def get_sale_date(date_string):
    date_list = date_string.split()
    clean_date_string = ' '.join(date_list[1:])
    try:
        sale_date = dateutil.parser.parse(clean_date_string).date()
    except ValueError:
        sale_date = dateutil.parser.parse(date_string, fuzzy=True).date()
    return sale_date


def is_heading(this_line):
    has_cattle = re.search(r'\:',this_line)
    is_succinct = len(this_line.split()) < 6
    return bool(has_cattle and is_succinct)


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = re.search(r'\$[0-9]+?', this_line)
    has_dash = re.search('\u2013', this_line)
    is_not_succinct = len(this_line.split()) > 2
    
    return (has_price or has_dash) and is_not_succinct


def is_number(string):

    string = re.sub(r'\$|[,-/]|cw?t?|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale_head(this_line):
    head_list = this_line.split()
    head_string = head_list[1].replace(',','')
    return head_string


def get_sale_location(sale_location):
    sale_location = ' '.join(sale_location)
    if '-' in sale_location:
        sale_location = sale_location.split('-')
        name = sale_location[0]
        if ',' in sale_location[1]:
            sale_location = sale_location[1].split(',')
            city = sale_location[0]
            state = sale_location[1]
        else:
            match = re.search(r'(.*)(' + scrape_util.state + r')', sale_location[1], re.IGNORECASE)
            if match:
                city = match.group(1)
                state = match.group(2)
            else:
                city = sale_location[1]
                state = ''
    else:
        name = sale_location
        city = ''
        state = ''
        
    sale = {
        'consignor_name': name.strip(),
        'consignor_city': city.title().strip(),
        'consignor_state': state.strip(),
        }

    return sale


def get_sale(sale_list, cattle):
    number_word = list(idx for idx, elem in enumerate(sale_list) if is_number(elem))
    head_string = sale_list[0]
    sale = {'cattle_head': head_string}
    cattle_string = cattle +' '+ ' '.join(sale_list[number_word[0]+1:number_word[-1]])
    if '#' in cattle_string:
        cattle_list = cattle_string.split()
        cattle_string = ' '.join(cattle_list[:-1])
        weight_string = cattle_list[-1].replace('#','')
        sale['cattle_avg_weight'] = weight_string
        
    sale['cattle_cattle'] = cattle_string
    price_string = sale_list[-1]
    price_string = price_string.replace('$', '')
    price_string = price_string.replace(',', '')
    sale['cattle_price'] = price_string

    sale = {k: v for k, v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    cattle = ''
    for this_line in line:

        if is_heading(this_line):
            cattle = this_line.replace(':', '').title()

        if is_sale(this_line):
            this_line = re.sub(r'(?<=[^0-9])-|' + '\u2013', ' - ', this_line, count=1).split()
            dash_idx = next((i for i, v in enumerate(this_line) if v=='-'), -1)
            number_word = list(i for i, v in enumerate(this_line) if is_number(v) and i > dash_idx)
            if not number_word or number_word[0]!=0:
                sale = this_default_sale.copy()
                if number_word:
                    sale_location = get_sale_location(this_line[:number_word[0]])
                    sale_list = this_line[number_word[0]:number_word[-1]+1]
                else:
                    sale_location = get_sale_location(this_line)
                    sale_list = []
                sale.update(sale_location)
            else:
                sale_list = this_line

            if len(sale_list)>3:
                sale.update(get_sale(sale_list, cattle))
                writer.writerow(sale)


def main():            

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Get to the category page to find any report
    request = Request(
        blog_url,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    div = soup.find('span', attrs={'class': 'PostHeader'})
    href = div.a['href']
    request = Request(
        href,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())

    # Get the starting report
    link = soup.find('link', attrs={'rel': 'start'})
    report = Report(link)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        sale_date = get_sale_date(this_report[0])
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        line = this_report[1].get_text()
        if re.search(r'\b(colt|filly|stallion)\b', line, re.IGNORECASE):
            line = []
        else:
            line = line.split('\n')

        with io_name.open('w') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
