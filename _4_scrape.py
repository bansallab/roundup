import csv
import requests
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


which_button = 0
default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t'
    

def is_sale(word, last_cattle):
    cattle_clue = scrape_util.default_cattle_clue
    this_cattle = re.match(cattle_clue, word[0], re.IGNORECASE)
    if this_cattle:
        last_cattle = this_cattle.string
    has_cattle = bool(last_cattle)
    price_clue = r'[0-9,]*\.[0-9]{2}'
    has_price = bool(re.search(price_clue, ' '.join(word)))
    return (has_cattle & has_price, last_cattle)


def get_sale_date(date_string):
    sale_date = parser.parse(date_string)
    return sale_date


def get_sale_head(line):

    for this_line in line:
        if re.search(r'head',this_line,re.IGNORECASE):
            word = this_line.split()
            for idx in range(0,len(word)):
                if re.search(r'head',word[idx],re.IGNORECASE):
                    head_pos = idx
                    break
            if head_pos == len(word)-1:
                try:
                    return int(word[head_pos-1].replace(',',''))
                except ValueError:
                    pass
            else:
                line_separated = re.split(r'head', this_line, flags = re.IGNORECASE)
                match = re.search(r'([0-9]+)',line_separated[1])
                if match:
                    return match.group(1)

    pass


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')$', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location
                

def get_sale(word, last_cattle):

    n_number_word = sum(scrape_util.is_number(this_word) for this_word in word)

    cattle_clue = r'(white|face|black|red|mixed|angus|char|charolais|bwf|xbred|mot)$'
    n_cattle_word = 0
    add_last_cattle = True
    idx = -3
    try:
        while idx:
            if re.match(cattle_clue, word[idx], re.IGNORECASE):
                n_cattle_word += 1
                idx -= 1
            elif re.match(scrape_util.default_cattle_clue, word[idx], re.IGNORECASE):
                n_cattle_word += 1
                idx -= 1
                add_last_cattle = False
            else:
                idx = False
    except IndexError:
        return {}
    location_span = len(word) - (n_cattle_word + n_number_word)
    sale_location = get_sale_location(word[0:location_span])
    cattle_description = ' '.join(word[location_span + (n_number_word - 2):location_span + (n_number_word - 2) + n_cattle_word]).lower()
    if add_last_cattle:
        cattle_description += ' ' + last_cattle.lower()
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_cattle': cattle_description.strip(),
        'cattle_avg_weight': word[-2],
        'cattle_price_cwt': word[-1],
        }
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)
    if n_number_word == 3:
        sale['cattle_head'] = word[location_span]

    return sale


def main():

    # get URLs for historical reports
    response = requests.get(
        base_url,
        headers=scrape_util.url_header,
        )
    soup = BeautifulSoup(response.content, 'lxml')
    button = soup.find('select', attrs = {'name' : 'reportID' })
    option = button.find_all('option')
    report = []
    for this_option in option:
        if this_option['value']:
            report.append((this_option.get_text(), base_url[:-1] + "?reportID=" + this_option['value']))
            
    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)
            
    # write csv file for each historical report
    for this_report in report:

        this_date = this_report[0]
        sale_date = get_sale_date(this_date)

        # skip existing files
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        response = requests.get(
            this_report[1],
            headers=scrape_util.url_header,
            )
        soup = BeautifulSoup(response.content, 'lxml')
        div = soup.find_all('div', attrs={'class': 'sml'})[2]
        div.table.extract()
        line = div.get_text().splitlines()
        line = list(filter(bool, line))
        line = [this_line for this_line in line if this_line.strip() != '']

        # sale date
        sale_head = get_sale_head(line)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()

            # record sales
            last_cattle = ''
            for this_line in line:
                word = this_line.split()
                is_sale_bool, last_cattle = is_sale(word, last_cattle)
                if is_sale_bool:
                    # extract sale dictionary
                    sale = this_default_sale.copy()
                    sale.update(get_sale(word, last_cattle))
                    if sale != this_default_sale:
                        writer.writerow(sale)


if __name__ == '__main__':
    main()
