import csv
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util
from datetime import date


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_url = 'pastmarketreports.html'
first_year = 2014
strip_char = ':;,. \n\t-'


def get_sale_date(link, year):
    """Return the date of the livestock sale."""

    sale_date = dateutil.parser.parse(link)
    sale_date = sale_date.replace(year=year)
        
    return sale_date


def is_heading(this_line):
    """Determine whether a given line is a section header 
    that describes subsequent lines of a report.
    """
    cattle_clue = '(bulls?|steers?|cows?|heiferettes?|heifers?|calves|pairs?)'
    has_cattle = re.search(cattle_clue, this_line, re.IGNORECASE)
    is_succinct = len(this_line.split()) < 3
   
    return bool(has_cattle and is_succinct)


def is_sale(td_text, tr):

    text = ' '.join(td_text)

    result = True

    if result and not any(td_text):
        result = False

    if result and not has_span(tr):
        result = False

    if result and tr.find('strong'):
        result = False

    if result and re.search(r'sold for', text, re.IGNORECASE):
        result = False

    if result and is_number(td_text[1]):
        result = False

    if result and re.search(r'\d+\s+TO\s+\d+', text):
        result = False

    return result


def has_span(this_tr):
    is_span = False
    
    if len(this_tr.find_all('span')) > 1 or len(this_tr.text) == 10:
        is_span = True

    return is_span


def is_number(string):
    """Test whether a string is numeric. Ignoring units like 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale(td_text, heading):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    name = ''
    city = ''
    state = ''
    if re.search(r'consignor', td_text[0], re.IGNORECASE):
        match = re.search(scrape_util.state, td_text[0], re.IGNORECASE)
        state = match.group(0)
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + r')', td_text[1], re.IGNORECASE)
        name = td_text[0]
        if match:
            city = match.group(1)
            state = match.group(2)

    sale = {
        'consignor_name': name.strip(),
        'consignor_city': city.strip().title(),
        'consignor_state': state.strip(),
        }

    cattle = td_text[2].split()
    if is_number(cattle[0]):
        sale['cattle_head'] = cattle.pop(0)

    cattle = ' '.join([heading] + cattle)
    sale.update({
        'cattle_cattle': cattle.strip(),
        'cattle_avg_weight': td_text[3].replace(',', '').strip(),
        })

    price_string = td_text[4].replace(',', '').strip()
    if '/HD' in price_string:
        price = 'cattle_price'
        price_string = price_string.replace('/HD', '')
    else:
        price = 'cattle_price_cwt'
    sale[price] = price_string

    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(tr, writer, this_default_sale):
    """Extract sales from a list of report lines and write them to a CSV file."""

    heading = ''
    
    for this_tr in tr:
        sale = this_default_sale.copy()
        text = this_tr.text
        td_text = list(td.text.replace('\xa0', ' ').strip(strip_char) for td in this_tr.find_all('td'))
        if not is_heading(text) and is_sale(td_text, this_tr):
            sale.update(get_sale(td_text, heading))
            writer.writerow(sale)
        elif is_heading(text):
            heading = text.strip(strip_char)


def main():

    archive = scrape_util.ArchiveFolder(argv, prefix)

    # "pastmarketreports" with consistent style begin in 2014, around April
    # the try .. except block below 'handles' the old style by skipping it
    for year in range(first_year, date.today().year + 1):

        request = Request(
            base_url + str(year) + report_url,
            headers=scrape_util.url_header
            )

        try:
            with urlopen(request) as io:
                soup = BeautifulSoup(io.read())
        except HTTPError:
            break

        div = soup.find_all('div', attrs={'class': 'blockbody'})
        report = [this_div.table.table for this_div in div if this_div.table.find('table')]

        for this_report in report:

            tr = this_report.find_all('tr')
            header = ' '.join(td.get_text() for td in tr.pop(0).find_all('td'))
            header = re.sub(r'market report', '', header, flags=re.IGNORECASE)
            while header.strip(' -')=='':
                header = ' '.join(td.get_text() for td in tr.pop(0).find_all('td'))
                header = re.sub(r'market report', '', header, flags=re.IGNORECASE)
            try:
                sale_date = get_sale_date(header.strip(), year)
            except:
                continue

            io_name = archive.new_csv(sale_date)
            if not io_name:
                continue

            this_default_sale = default_sale.copy()
            this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                'sale_head': '',
                })

            with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()
                write_sale(tr, writer, this_default_sale)


if __name__ == '__main__':
    main()
