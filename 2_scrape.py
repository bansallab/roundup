import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


which_button = 3
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path_1 = 'marketreport.php'
report_path_2 = 'market-reports.php?reportID='


def has_range(word):
    """True for phrases like "sold steady 175.00 to 180.00", which indicate non-sale records."""
    test = False
    ct = 0
    
    while not(test) and ct + 2 < len(word):
        test = scrape_util.is_number(word[ct])
        test = test and word[ct + 1].lower() == 'to'
        test = test and scrape_util.is_number(word[ct + 2])
        ct += 1

    return test
    

def is_sale(word):
    """True for phrases like "Gomez [Jackson[, WY]] 3 {hfr|cow|steer} 455 270.0 {C|H}?"."""
    if word[-1] in ['C', 'H']:
        word.pop()
    cattle_clue = scrape_util.default_cattle_clue
    price_clue = r'[0-9,]*\.[0-9]{2}'
    has_cattle = any(bool(re.match(cattle_clue, this_word, re.IGNORECASE)) for this_word in word)
    has_price_and_weight = re.match(price_clue, word[-1]) and scrape_util.is_number(word[-2])
    has_keyword = {'sold'} <= set(this_word.lower() for this_word in word)
    has_keyphrase = has_range(word)

    return has_cattle and has_price_and_weight and not(has_keyword or has_keyphrase)
        

def get_sale_date(date_string):
    sale_date = parser.parse(date_string)
    return sale_date


def get_sale_head(line):

    for this_line in line:
        if re.search(r'hd|head',this_line,re.IGNORECASE):
            try:
                week_string, head_string = re.split(',', this_line)
                match = re.search(r'([0-9]+)',head_string)
                if match:
                    return match.group(1)
            except ValueError:
                pass


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

    # number words separate consignor_name (when it is explicit) and cattle type
    cattle_clue = scrape_util.default_cattle_clue
    idx_cattle_word = [idx for idx in range(len(word)) if re.match(cattle_clue, word[idx], re.IGNORECASE)]
    idx_number_word = [idx for idx in range(idx_cattle_word[0], len(word)) if scrape_util.is_number(word[idx])]
    idx_head = [idx for idx in range(idx_cattle_word[0]) if scrape_util.is_number(word[idx])]
    if idx_head:
        idx_number_word.insert(0, idx_head[-1])
    n_number_word = len(idx_number_word)

    # the length of idx_number_word may not be consistent
    sale = {
        'cattle_head': word[idx_number_word[0]],
        'cattle_cattle': ' '.join(word[idx_number_word[0] + 1:idx_number_word[1]]).lower(),
        'cattle_price_cwt': word[idx_number_word[-1]].replace(',', ''),
        }

    idx_brace_word = [idx for idx in range(len(word)) if re.search(r'[\[\]]', word[idx])]            
    if len(idx_brace_word)==1:
        idx_brace_word.append(next(idx for idx in idx_number_word if idx > idx_brace_word[0]))

    if idx_brace_word:
        sale['consignor_name'] = ' '.join(word[0:idx_brace_word[0]]).strip('*')
        sale_location = get_sale_location(word[idx_brace_word[0] + 1:idx_brace_word[1]])
        sale['consignor_city'] = sale_location.pop(0).strip().title()
        if sale_location:
            sale['consignor_state'] = sale_location.pop().strip()

    if n_number_word == 3:
        sale['cattle_avg_weight'] = word[idx_number_word[1]].replace(',', '')
    elif n_number_word == 2 and '.' in word[-1]:
        pass
    else:
        raise NameError('Unexpected sale data!')

    return sale


def main():

    # Get URLs for historical reports
    request = Request(
        base_url + report_path_1,
        headers=scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    button = soup.find_all('select', attrs = {'class' : 'reg' })[which_button]
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
            soup = BeautifulSoup(io.read())
        line = soup.get_text().splitlines()
        line = list(this_line for this_line in line if this_line.strip())

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

        io_name = archive.new_csv(sale_date)
        if not io_name:
            break

        # Open CSV file and write header
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
                    writer.writerow(sale)                        


if __name__ == '__main__':
    main()
