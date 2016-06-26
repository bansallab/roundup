import csv
from urllib.request import Request, urlopen
import urllib.error
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market_reports.html'
strip_char = ';,. \n\t'


def get_sale_date(this_report):
    text = this_report['href']
    match = re.search(r'[0-9]{,2}[-][0-9]{,2}[-][0-9]{,4}\.', text)
    if not match:
        text = this_report.get_text()
        match = re.search(r'[0-9]+[/][0-9]+[/][0-9]+', text)
    if match:
        date_string = match.group(0)
        sale_date = parser.parse(date_string)

    return sale_date


def get_sale_head(soup):

    td = soup.find('td', attrs={'colspan':4})
    if not td:
        pattern = re.compile(r'[0-9,]+ +head', flags=re.IGNORECASE)
        text = soup.find(text=pattern)
    else:
        text = td.get_text()

    if text:
        text = text.replace('\n','').replace('\xa0','')
        stop = text.find('.')
        match = re.findall(r'([0-9,]+) +head', text[:stop], flags=re.IGNORECASE)
        if not match:
            sale_head = None
        else:
            sale_head = 0
            for this_match in match:
                sale_head += int(this_match.replace(',',''))
    else:
        sale_head = None

    return sale_head


def is_sale(this_row):

    is_sale = False
    td = list(this_td for this_td in this_row.find_all('td') if this_td.get_text())
    if len(td) > 3:
        if re.match(r'[0-9]', td[0].get_text().strip()):
            is_sale = True

    return is_sale


def is_heading(this_row):

    has_cattle = False
    has_number = False
    td = list(this_td for this_td in this_row.find_all('td') if this_td.get_text())
    cattle_clue = r'(bulls?|steers?|strs?|cows?|heifers?|heiferettes?|hfrs?|calf|calves|pairs?)'
    if td:
        if re.search(cattle_clue, td[0].get_text(), re.IGNORECASE):
            has_cattle = True
        for this_td in td:
            if re.search(r'[0-9]', this_td.get_text()):
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
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_head': word[number_word[0]].strip(strip_char),
        'cattle_cattle': cattle_string.strip(strip_char),
        }

    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    price_string = word[number_word[-1]]
    match = re.search(r'/?hd', price_string, re.IGNORECASE)
    if match:
        sale['cattle_price'] = re.sub(r'\$|/?hd|,', '', price_string, flags = re.IGNORECASE).strip(strip_char)
    else:
        sale['cattle_price_cwt'] = re.sub(r'\$|/?cwt|,', '', price_string, flags = re.IGNORECASE).strip(strip_char)

    if len(number_word) > 2:
        sale['cattle_avg_weight'] = word[number_word[1]].strip(strip_char).replace(',', '')

    sale = {k:v for k,v in sale.items() if v}

    return sale


def write_sale(line, default_sale, writer):

    for this_line in line:
        if is_heading(this_line):
            cattle = this_line.find_all('td')[0].get_text()
            cattle = re.sub(r'\s+', ' ', cattle).strip(strip_char)
        elif is_sale(this_line):
            text = this_line.get_text()
            word = text.split()
            sale = default_sale.copy()
            sale.update(get_sale(word, cattle))
            if sale != default_sale:
                writer.writerow(sale)


def main():

    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    table = next(
        this_table for this_table in soup.find_all('table')
        if not this_table.tr.table and 'ARCHIVED MARKET REPORTS' in this_table.tr.get_text()
        )
    report = (
        this_a for this_a in table.find_all('a')
        if this_a.get('href') and 'Greeley' in this_a.get('href')
        )

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:

        # sale defaults
        sale_date = get_sale_date(this_report)

        # Skip if already archived
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        # query this_report for sale data
        try:
            href = this_report['href']
            if 'http' in href:
                url = href
            else:
                url = base_url + this_report['href']
            request = Request(
                url,
                headers=scrape_util.url_header,
                )
            with urlopen(request) as io:
                soup = BeautifulSoup(io.read(), 'lxml')
        except urllib.error.HTTPError:
            print('HTTP error: {}'.format(url))
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        line = soup.find_all('tr')
        if line:
            this_default_sale['sale_head'] = get_sale_head(soup)

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
