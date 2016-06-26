import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util

default_sale, base_url, prefix = scrape_util.get_market(argv)
base_url += 'index.cfm'
report_path = ['?show=10&mid=7', '?show=10&mid=8']
strip_char = ';,.# \n\t'


def get_sale_title(this_report):
    """Return the title of the livestock sale."""

    title_string = this_report.find('tr').find('td').find('span').get_text()
    try:
        separator = re.compile('from', flags=re.IGNORECASE)
        topprice, sale_title = separator.split(title_string)
        sale_title = sale_title.strip(strip_char)
    except ValueError:
        sale_title = title_string
    return sale_title


def get_sale_date(this_report):
    """Return the date of the livestock sale."""

    tr = this_report.find_all('tr')
    dateheader_string = tr[1].find('td').string
    dateheader_string = re.sub(r'\s',' ',dateheader_string)
    date_string, head_string = re.split(r' {2,}', dateheader_string)
    sale_date = dateutil.parser.parse(date_string)
    return sale_date


def get_sale_head(this_report):
    """Return the head of the livestock sale."""

    tr = this_report.find_all('tr')
    dateheader_string = tr[1].find('td').string
    dateheader_string = re.sub(r'\s',' ',dateheader_string)
    date_string, head_string = re.split(r' {2,}', dateheader_string)
    match = re.search(r'([0-9]+)', head_string)
    if match:
        return match.group(1)


def is_empty(this_line):
    
    empty = True
    for x in this_line:
        if is_not_blank(x.string):
            empty = False
            break
    return empty
    

def is_description(this_line):
    """Determine whether a given line is a description of the sale."""
    
    non_blank_word = list(idx for idx in range(len(this_line)) if is_not_blank(this_line[idx].string))
    is_succinct = len(non_blank_word) < 3
    is_not_bolded = True
    for x in this_line:
        if x.find('strong'):
            is_not_bolded = False
            break

    return bool(is_succinct and is_not_bolded)


def is_heading(this_line):
    """Determine whether a given line is a section header
    that describes subsequent lines of a report.
    """

    cattle_clue = '(bulls?|steers?|cows?|heiferettes?|heifers?|calves|pairs?)'
    has_cattle = re.search(cattle_clue, this_line[0].string, re.IGNORECASE)
    non_blank_word = list(idx for idx in range(len(this_line)) if is_not_blank(this_line[idx].string))
    is_succinct = len(non_blank_word) < 3
    is_bolded = False
    for x in this_line:
        if x.find('strong'):
            is_bolded = True
            break

    return bool(has_cattle and is_succinct and is_bolded)


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = False
    for x in this_line:
        if re.search(r'[0-9]+\.[0-9]{2}', x.string):
            has_price = True
            break
    non_blank_word = list(idx for idx in range(len(this_line)) if is_not_blank(this_line[idx].string))
    is_not_succinct = len(non_blank_word) > 3

    return bool(has_price and is_not_succinct)


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
    """Test whether a string is numeric. Ignoring units like 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-/]|#|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def is_not_blank(string):
    """Test whether a string is not blank."""

    string = re.sub(r'\s','',string)
    if string == '':
        return False
    else:
        return True


def get_sale(word, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))

    sale_location = get_sale_location(word[:1])
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_cattle': cattle + ' ' +  word[2]
        }

    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    head_string = word[number_word[0]].strip(strip_char).replace(',','')
    try:
        float(head_string)
        sale.update({'cattle_head': head_string})
    except ValueError:
        pass

    if len(number_word) > 2:
        weight_string = word[number_word[1]].strip(strip_char).replace(',', '')
        try:
            float(weight_string)
            sale.update({'cattle_avg_weight': weight_string})
        except ValueError:
            pass

    price_string = word[number_word[len(number_word)-1]]
    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',','').strip(strip_char)

    sale = {k:v for k,v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    cattle = ''

    for this_line in line:
        if is_empty(this_line):
            pass
        elif is_description(this_line):
            pass
        elif is_heading(this_line):
            cattle = this_line[0].string
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            word = []
            for x in this_line:
                word.append(x.string)
            sale.update(get_sale(word, cattle))
            writer.writerow(sale)


def main():

    # Get URLs for all reports
    for this_report_path in report_path:
        request = Request(
            base_url + this_report_path,
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read(), 'lxml')
        # content = soup.find('table', id = 'mainWrapper')
        # report = content.find('table').find('table').find_all('table')
        report = [table for table in soup.find_all('tbody') if not table.tbody]

        # Locate existing CSV files
        archive = scrape_util.ArchiveFolder(argv, prefix)

        # Write a CSV file for each report not in the archive
        for this_report in report:

            sale_date = get_sale_date(this_report)
            io_name = archive.new_csv(sale_date)

            # Skip iteration if this report is already archived
            if not io_name:
                continue

            # Initialize the default sale dictionary
            this_default_sale = default_sale.copy()
            sale_title = get_sale_title(this_report)
            sale_head = get_sale_head(this_report)
            this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                'sale_title': sale_title,
                'sale_head': sale_head,
                })

            # Read the report text into a list of lines
            line1 = []
            line2 = []
            for tr in this_report.find_all('tr'):
                td = tr.find_all('td')

                if len(td) == 11:
                    pass
                else:
                    for x in range(10):
                        try:
                            if int(td[x]['colspan']) > 1:
                                for y in range(x+1, x+int(td[x]['colspan'])):
                                    newtag = soup.new_tag("td")
                                    newtag.string = ' '
                                    td.insert(y,newtag)
                        except KeyError:
                            continue
                newline = [td[idx] for idx in range(5)]
                newline2 = [td[idx] for idx in range(6, 11)]
                line1.append(newline)
                line2.append(newline2)

            line = line1 + line2
            line[0:2] = []

            # Open a new CSV file and write each sale
            with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()
                write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
