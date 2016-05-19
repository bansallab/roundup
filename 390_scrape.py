import csv
from urllib.request import Request, urlopen
import urllib.error
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import date
import xlrd
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market_reports.html'
min_date = date(2014, 10, 1)


def get_sale_date(this_report):
    text = this_report['href']
    match = re.search(r'[0-9]{,2}[-][0-9]{,2}[-][0-9]{,4}\.', text)
    if not match:
        text = this_report.get_text()
        match = re.search(r'[0-9]+[/][0-9]+[/][0-9]+', text)
    if match:
        date_string = match.group(0)
        sale_date = parser.parse(date_string).date()

    return sale_date


def is_sale(this_row):

    is_sale = False
    td = [td for td in this_row if td]
    if len(td) > 3:
        if re.match(r'[0-9]', td[0]):
            is_sale = True

    return is_sale


def is_heading(this_row):

    has_cattle = False
    has_number = False
    td = [td for td in this_row if td]
    cattle_clue = r'(bulls?|steers?|strs?|cows?|heifers?|heiferettes?|hfrs?|calf|calves|pairs?)'
    if td:
        if re.search(cattle_clue, td[0], re.IGNORECASE):
            has_cattle = True
        for this_td in td:
            if re.search(r'[0-9]', this_td):
                has_number = True
                break

    return has_cattle and not has_number


def is_number(string):
    string = re.sub(r'\$|/?cwt|/?hd|,', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale_location(word):

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


def get_sale(word, cattle):

    match = re.search(r'([0-9]+)[^0-9]', word[0])
    if match:
        word[0] = word[0].replace(match.group(1), '')
        word.insert(0, match.group(1))

    number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))
    sale_location = get_sale_location(word[number_word[-1] + 1:])
    cattle_string = ' '.join(word[number_word[0] + 1:number_word[1]]) + ' ' + cattle
    sale = {
        'consignor_city': sale_location.pop(0).strip().title(),
        'cattle_head': word[number_word[0]].strip(),
        'cattle_cattle': cattle_string.strip(),
        }

    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip()

    cattle_weight = ''
    if len(number_word)==3:
        cattle_weight = word[number_word[1]]
    elif len(number_word)==4:
        cattle_weight = word[number_word[2]]
    sale['cattle_avg_weight'] = cattle_weight.strip().replace(',', '')

    price_string = word[number_word[-1]]
    price_type = 'cattle_price_cwt'
    if re.search(r'/?hd', price_string, re.IGNORECASE):
        price_type = 'cattle_price'
    if 'bred cows' in cattle.lower():
        price_type = 'cattle_price'
    price_string = re.sub(r'[^0-9\.]', '', price_string)
    sale[price_type] = price_string

    sale = {k:v for k,v in sale.items() if v}

    return sale


def write_sale(line, default_sale, writer):

    # extract & write sale dictionary
    cattle = None
    for this_line in line:
        if is_heading(this_line):
            cattle = this_line[0]
            cattle = re.sub(r'\s+', ' ', cattle).strip()
        elif cattle and is_sale(this_line):
            sale = default_sale.copy()
            sale.update(get_sale(this_line, cattle))
            if sale != default_sale:
                writer.writerow(sale)


def main():

    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    table = next(
        this_table for this_table in soup.find_all('table')
        if not this_table.tr.table and 'ARCHIVED MARKET REPORTS' in this_table.tr.get_text()
        )
    report = (
        this_a for this_a in table.find_all('a')
        if this_a.get('href') and 'Madera' in this_a.get('href')
        )

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:

        # sale defaults
        sale_date = get_sale_date(this_report)
        if sale_date < min_date:
            continue

        # Skip if already archived
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        # query this_report for sale data
        href = this_report['href']
        if 'http' in href:
            url = href
        else:
            url = base_url + this_report['href']
        request = Request(
            url,
            headers=scrape_util.url_header,
            )
        try:
            with urlopen(request) as io:
                response = io.read()
        except urllib.error.HTTPError:
            print('HTTP error: {}'.format(url))
            continue

        match = re.search(r'\.(xlsx?)$', url, re.IGNORECASE)
        if match:
            temp_raw = scrape_util.ReportRaw(argv, prefix, suffix=match.group(1))
            with temp_raw.open('wb') as io:
               io.write(response)
            sheet = xlrd.open_workbook(str(temp_raw)).sheet_by_index(0)
            line = [[re.sub(r'\.0$', '', str(td)) for td in sheet.row_values(idx)] for idx in range(0, sheet.nrows)]
            temp_raw.clean()
        else:
            soup = BeautifulSoup(response)
            # line = [[td.get_text() for td in tr.find_all('td')] for tr in soup.find_all('tr')]
            line = [
                [re.sub(r'\r|\n', '', text) for text in re.split(r'\xa0+', p.get_text())]
                for p in soup.find_all('p', attrs={'class': 'ListParagraphCxSpMiddle'})
                ]

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
