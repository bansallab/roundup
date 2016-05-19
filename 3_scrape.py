
import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


which_button = 2
default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path_1 = 'marketreport.php'
report_path_2 = 'market-reports.php?reportID='


def has_range(word):
    test = False
    ct = 0
    
    while not(test) and ct + 2 < len(word):
        test = scrape_util.is_number(word[ct])
        test = test and word[ct + 1].lower() == 'to'
        test = test and scrape_util.is_number(word[ct + 2])
        ct += 1

    return test
    

def is_sale(word):
    cattle_clue = scrape_util.default_cattle_clue
    price_clue = r'[0-9,]*\.[0-9]{2}'
    has_cattle = any(bool(re.match(cattle_clue, this_word, re.IGNORECASE)) for this_word in word)
    has_price_and_weight = re.match(price_clue, word[-1]) and scrape_util.is_number(word[-2])
    has_keyword = {'sold'} <= set(this_word.lower() for this_word in word)
    has_keyphrase = has_range(word)

    return has_cattle and has_price_and_weight and not(has_keyword or has_keyphrase)
        

def get_sale_date(date_string, line):
    sale_date = parser.parse(date_string).date()
    if sale_date.weekday() != 1:
        for this_line in line:
            match = re.search('receipts tuesday,(.*?\d{4})', this_line, re.IGNORECASE)
            if match:
                sale_date = parser.parse(match.group(1)).date()
                break
    return sale_date


def get_sale_head(line):

    for this_line in line:
        if re.search(r'receipt',this_line,re.IGNORECASE):
            match = re.search(r'([0-9]+)',this_line)
            if match:
                return match.group(1)


def get_sale(word, last_consignor):

    # number words separate consignor_name (when it is explicit) and cattle type
    cattle_clue = scrape_util.default_cattle_clue
    cattle_word = [idx for idx in range(len(word)) if re.match(cattle_clue, word[idx], re.IGNORECASE)]
    idx_number_word = [idx for idx in range(cattle_word[0], len(word)) if scrape_util.is_number(word[idx])]
    idx_number_word.insert(0, [idx for idx in range(cattle_word[0]) if scrape_util.is_number(word[idx])][-1])
    n_number_word = len(idx_number_word)

    # the length of idx_number_word may not be consistent
    sale = {
        'cattle_head': word[idx_number_word[0]],
        'cattle_cattle': ' '.join(word[idx_number_word[0] + 1:idx_number_word[1]]).lower(),
        'cattle_price_cwt': word[idx_number_word[-1]],
        }
        
    if idx_number_word[0] == 0:
        sale['consignor_name'] = last_consignor
    else:
        sale['consignor_name'] = ' '.join(word[0:idx_number_word[0]]).title()

    if n_number_word == 3:
        sale['cattle_avg_weight'] = word[idx_number_word[1]]
    elif n_number_word == 2 and '.' in word[-1]:
        pass
    else:
        raise NameError('Unexpected sale data!')

    return sale, sale['consignor_name']


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
        line = [v.strip() for v in soup.get_text().splitlines()]
        line = []
        for v in soup.get_text().splitlines():
            split = re.split(r'(?<=\.\d{2})\s+(?=\d)', v)
            line.extend([v.strip() for v in split if v.strip()])

        # sale date
        sale_date = get_sale_date(this_date, line)
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
            last_consignor = ''
            for this_line in line:
                word = this_line.split()

                if is_sale(word):
                    # extract sale dictionary
                    sale = this_default_sale.copy()
                    this_sale, last_consignor = get_sale(word, last_consignor)
                    sale.update(this_sale)
                    writer.writerow(sale)                        


if __name__ == '__main__':
    main()
