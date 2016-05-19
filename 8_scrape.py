import csv
from urllib.request import Request, urlopen
import urllib.error
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t\$'
report_path = '/Cow_Sales/CS_PastSales.html'


def is_sale(word):

    is_not_succinct = len(word) > 2
    has_number = False
    for this_word in word:
        if re.search(r'[0-9]', this_word):
            has_number = True
            break

    return bool(is_not_succinct and has_number)


def get_sale_head(table, io_name):
    """Return the head of the livestock sale."""

    head = None

    # Special Case
    if io_name == 'billings_livestock_08-09-25.csv':
        tr = table.find_all('tr')[1]
    else:
        tr = table.find('tr')

    header_line = tr.get_text()
    header_line = re.sub(r'(\n)+', '\n', header_line)
    header_line = re.sub(r'(\r\n)|(\xa0)', '', header_line)
    header_word = header_line.strip('\n').split('\n')
    head_string_loc = list(idx for idx in range(len(header_word)) if re.search(r'hd|head',header_word[idx],re.IGNORECASE))
    if len(head_string_loc) == 0:
        pass
    elif len(head_string_loc) > 1:
        pass
    else:
        try:
            date_string, head_string = re.split(r'~|-|\u2013', header_word[head_string_loc[0]])
        except ValueError:
            try:
                date_string, year_string, head_string = re.split(r', ', header_word[head_string_loc[0]])
            except ValueError:
                head_string = header_word[head_string_loc[0]]
        match = re.search(r'([0-9,.]+)', head_string)
        if match:
            head = re.sub(r'[,.]', '', match.group(1))
    
    return head


def get_sale_date(this_report):

    date_string = re.search(r'([0-9]+)[-_]+([0-9]+)[-_]+([0-9]+)', this_report['href'])
    date_string = date_string.group(1) + '-' + date_string.group(2) + '-' + date_string.group(3)
    try:
        sale_date = parser.parse(date_string)
    except ValueError:
        date_string = this_report.get_text().strip().replace('_','-')
        sale_date = parser.parse(date_string)

    # Special Case
    if re.search(r'12_13-15_12', this_report['href']):
        sale_date = parser.parse('12-13-12')
    
    return sale_date


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

    match = re.search(r'([0-9]+)\s+[^0-9]', word[2])
    if match:
        word[2:3] = [match.group(1), word[2].replace(match.group(1), '').strip()]

    sale = {
        'consignor_name': word[0].strip(strip_char),
        'cattle_head': word[2].replace(',', ''),
        'cattle_cattle': word[3].strip(strip_char),
        'cattle_avg_weight': word[4].replace(',', '').strip(strip_char),
        }

    if re.search(r'[0-9]{5}', word[1]):
        sale['consignor_zip'] = word[1].strip(strip_char)
    else:
        sale['consignor_city'] = word[1].strip(strip_char).title()

    try:
        float(sale['cattle_avg_weight'])
    except ValueError:
        sale.pop('cattle_avg_weight')

    if len(word)==6:
        price_string = word[5]
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


def main():

    # get URLs for historical reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    section = soup.find('div', attrs = {'class' : 'Section1'})
    report = [a for a in section.find_all('a') if 'Past_Sales' in a['href']]

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        # sale defaults
        sale_date = get_sale_date(this_report)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        if sale_date.year < 2013:
            continue

        # skip if already archived
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        request = Request(
            base_url + '/Cow_Sales/' + this_report['href'],
            headers = scrape_util.url_header,
            )
        try:
            with urlopen(request) as io:
                soup = BeautifulSoup(io.read())
        except urllib.error.HTTPError:
            continue

        table = soup.find_all('table')
        this_default_sale['sale_head'] = get_sale_head(table[0], io_name.name)

        table = table.pop()
        sub = re.compile(r'(\r\n)|(\xa0)')
        line = [[sub.sub(' ', td.get_text()) for td in tr.find_all('td')] for tr in table.find_all('tr')]

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            # sales
            for this_line in filter(bool, line):
                word = [word.strip(strip_char) for word in this_line]
                if is_sale(word):                    
                    # extract sale dictionary
                    sale = this_default_sale.copy()
                    sale.update(get_sale(word))
                    if sale != this_default_sale:
                        writer.writerow(sale)


if __name__ == '__main__':
    main()
