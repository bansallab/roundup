import csv
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'php/archives.php'
strip_char = ';,. \n\t\r'


def get_sale_date(date_string):
    """Get date of the sale"""

    sale_date = parser.parse(date_string)
    return sale_date


def get_sale_head(soup):
    """Get number of head of the sale"""

    td = soup.find('table', attrs = {'class': 'tablelefttop'}).find('tr').find_all('td')
    for idx in range(0,len(td)):
        if td[idx].string:
            head_match = re.match(r'head',td[idx].string,re.I)
            if head_match:
                head_idx = idx
                break

    head_string = td[head_idx + 1].string
    if head_string:
        match = re.search(r'([0-9]+)',head_string, re.I)
        if match:
            return match.group(1)


def is_sale(word):
    """Test if the line is a record of a sale"""

    cattle_clue = r'(bulls?|steers?|strs?|cows?|heifers?|hfrs?|calf|calves|pairs?|hc|sc)'
    price_clue = r'[0-9,]+'
    has_cattle = any(bool(re.search(cattle_clue, this_word, re.IGNORECASE)) for this_word in word)
    has_price = any(bool(re.search(price_clue, this_word)) for this_word in word)
    return has_cattle & has_price


def is_number(string):
    """Test whether a string is numeric. Ignoring units like 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-/]|cwt|he?a?d?|lb?s?\.?|pr\.?', '', string, flags = re.IGNORECASE)
    string = string.strip(strip_char)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale_location(sale_location):
    """Convert address strings into a list of address components."""

    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def get_sale(word):

    number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))
    consignor_name = word[0] + ' ' + word[1]
    consignor_name = consignor_name.strip(strip_char)
    sale_location = get_sale_location(word[number_word[0]-1])

    sale = {
        'consignor_name': consignor_name,
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        }

    cattle_string = word[number_word[0]+1].strip(strip_char)
    cattle_head_match = re.match(r'([0-9,]+) ', cattle_string)
    if cattle_head_match:
        sale['cattle_head'] = cattle_head_match.group(1).strip(strip_char)
        cattle_string = cattle_string.replace(cattle_head_match.group(1),'').strip(strip_char)

    sale['cattle_cattle'] = cattle_string

    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    if len(number_word) == 2:
        weight_string = word[number_word[0]].replace('lbs', '').strip(strip_char).replace(',','')
        try:
            float(weight_string)
            sale.update({'cattle_avg_weight': weight_string})
        except ValueError:
            pass

        price_string = word[number_word[1]]
        match = False
        if not match:
            match = re.search(r'([0-9,.]+)( ?/?he?a?d?\.?| ?/?pr?\.?)', price_string, re.IGNORECASE)
            key = 'cattle_price'
        if not match:
            match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
            key = 'cattle_price_cwt'
        if match:
            sale[key] = match.group(1).replace(',','').strip(strip_char)

    sale = {k:v for k,v in sale.items() if v}

    return sale


def main():

    # get URLs for historical reports
    request = Request(
        'http://www.glasgowstockyards.com/php/oldreports.php',
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    button = soup.find('select', attrs = {'class' : 'gsitxt2' })
    option = button.find_all('option')
    report = []
    for this_option in option:
        if this_option['value']:
            report.append((this_option.get_text(), this_option['value']))
            
    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:
        this_date = this_report[0]
        # sale date
        sale_date = get_sale_date(this_date)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # skip existing files
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        post_data = urlencode({'date': this_report[1], 'Submit': 'Submit'})
        request = Request(
            base_url + report_path,
            post_data.encode(),
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read())

        sale_head = get_sale_head(soup)
        this_default_sale['sale_head'] = sale_head

        table = soup.find_all('table', attrs={'class': False})[-1]
        line = []
        for tr in table.find_all('tr')[2:]:
            line_to_add = [td.get_text() for td in tr.find_all('td')]
            line.append(line_to_add)

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()

            for this_line in line:
                if is_sale(this_line):
                    # extract sale dictionary
                    sale = this_default_sale.copy()
                    sale.update(get_sale(this_line))
                    if sale != this_default_sale:
                        writer.writerow(sale)                        


if __name__ == '__main__':
    main()
