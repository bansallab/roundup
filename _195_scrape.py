import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path_1 = 'marketreport.php'
report_path_2 = 'market-reports.php?reportID='
strip_char = ';,. \n\t'


def is_sale(word):
    cattle_clue = scrape_util.default_cattle_clue
    price_clue = r'[0-9]+\.[0-9]{2}'
    has_cattle = any(bool(re.search(cattle_clue, this_word, re.IGNORECASE)) for this_word in word)
    has_price = any(bool(re.search(price_clue, this_word)) for this_word in word)
    return has_cattle & has_price


def get_sale_date(date_string):
    sale_date = parser.parse(date_string)
    return sale_date


def get_sale_head(line):
    for this_line in line:
        this_line = this_line.replace(',','')
        if re.search(r'\bhd\b|\bhead\b',this_line,re.IGNORECASE):
            match = re.search(r'([0-9]+)-([0-9]+)-([0-9]+)',this_line)
            if match:
                sale_string, head_string = this_line.split(match.group())
                match2 = re.search(r'([0-9]+)',head_string)
                if match2:
                    return match2.group(1)


def is_number(string):
    """Test whether a string is numeric. Ignoring units like 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


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


def get_sale(word):

    number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))
    sale = {
        'cattle_cattle': word[number_word[0]+1].strip(strip_char)
        }
    name_city = word[:number_word[0]]
    name_city_string = ' '.join(name_city).strip(',')
    name_city_list = name_city_string.split(',')
    if len(name_city_list) == 2:
        sale.update({'consignor_name': name_city_list[0].strip(strip_char)})
        sale.update({'consignor_city': name_city_list[1].strip(strip_char).title()})
    elif len(name_city_list) == 3:
        state_match = re.match(scrape_util.state, name_city_list[2].strip(strip_char), re.I)
        if state_match:
            sale.update({'consignor_state': name_city_list[2].strip(strip_char).upper()})
            sale.update({'consignor_city': name_city_list[1].strip(strip_char).title()})
            sale.update({'consignor_name': name_city_list[0].strip(strip_char)})
        else:
            sale.update({'consignor_city': name_city_list[2].strip(strip_char).title()})
            name_string = name_city_list[0] + ',' + name_city_list[1]
            sale.update({'consignor_name': name_string.strip(strip_char)})
    elif len(name_city_list) == 1:
        sale.update({'consignor_name': name_city_list[0].strip(strip_char)})

    if len(number_word) == 3:
        head_string = word[number_word[0]].strip(strip_char).replace(',','')
        try:
            int(head_string)
            sale.update({'cattle_head': head_string})
        except ValueError:
            pass
        weight_string = word[number_word[1]].strip(strip_char).replace(',','')
        try:
            float(weight_string)
            sale.update({'cattle_avg_weight': weight_string})
        except ValueError:
            pass
        price_string = word[number_word[2]]
        match = False
        if not match:
            match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
            key = 'cattle_price'
        if not match:
            match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
            key = 'cattle_price_cwt'
        if match:
            sale[key] = match.group(1).replace(',','').strip(strip_char)
    elif len(number_word) == 2:
        head_string = word[number_word[0]].strip(strip_char).replace(',','')
        try:
            int(head_string)
            sale.update({'cattle_head': head_string})
        except ValueError:
            pass
        price_string = word[number_word[1]]
        match = False
        if not match:
            match = re.search(r'([0-9,.]+) ?/?h?e?a?d?', price_string, re.IGNORECASE)
            key = 'cattle_price'
        if match:
            sale[key] = match.group(1).replace(',','').strip(strip_char)
    sale = {k:v for k,v in sale.items() if v}
    return sale


def main():

    # get URLs for historical reports
    request = Request(
        base_url + report_path_1,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    button = soup.find('select', attrs = {'class' : 'reg' })
    option = button.find_all('option')
    report = []
    for this_option in option:
        if this_option['value']:
            report.append((this_option.get_text(), base_url + report_path_2 + this_option['value']))
            
    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:
        this_date = this_report[0]
        request = Request(
            this_report[1],
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read(), 'lxml')
        text = re.sub(r'(\$[0-9.]+ \t)', r'\1\n', soup.get_text())
        line = text.splitlines()
        line = list(filter(bool, line))

        # sale date
        sale_date = get_sale_date(this_date)
        sale_head = get_sale_head(line)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # skip existing files
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()

            # sales
            for this_line in line:
                word = this_line.split()

                if is_sale(word):
                    # extract sale dictionary
                    sale = this_default_sale.copy()
                    sale.update(get_sale(word))
                    if sale != this_default_sale:
                        writer.writerow(sale)                        


if __name__ == '__main__':
    main()
