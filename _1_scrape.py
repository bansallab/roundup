import csv
import requests
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


which_button = 0
default_sale, base_url, prefix = scrape_util.get_market(argv)


def is_sale(word):
    cattle_clue = scrape_util.default_cattle_clue
    price_clue = r'(\$[0-9,]*\.[0-9]{2}|/HD)'
    has_cattle = any(bool(re.match(cattle_clue, this_word, re.IGNORECASE)) for this_word in word)
    has_price = any(bool(re.search(price_clue, this_word)) for this_word in word)
    return has_cattle & has_price


def get_sale_date(date_string):
    sale_date = parser.parse(date_string)
    return sale_date


def get_sale_head(line):
    for this_line in line:
        this_line = this_line.replace(',','')
        if re.search(r'hd|head',this_line,re.IGNORECASE):
            match = re.search(r'([0-9]+)',this_line)
            if match:
                return match.group(1)
            

def get_sale(word):
    cattle_clue = r'(mixed|mot|bla?c?k|white|red|char|b?wf|herf)'
    city_range = next(idx for idx in range(len(word)) if re.match(cattle_clue, word[idx], re.IGNORECASE))
    if city_range == 0:
        return {}
    number_range = next(idx for idx in range(len(word)) if scrape_util.is_number(word[idx]))
    sale = {
        'consignor_city': ' '.join(word[0:city_range]).title(),
        'cattle_cattle': ' '.join(word[city_range:number_range]).lower(),
        'cattle_avg_weight': word[number_range].replace(',', ''),
        }
    price_word = word[number_range + 1]
    if '/HD' in price_word:
        sale['cattle_price'] = price_word.strip('/HEAD').replace(',', '')
    else:
        sale['cattle_price_cwt'] = price_word.strip('$').replace(',', '')
        
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
        text = re.sub(r'(\$[0-9.]+ \t)', r'\1\n', div.get_text())
        line = text.splitlines()
        line = list(filter(bool, line))
        if re.search('estimating', line[0], re.IGNORECASE):
            continue

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

            # sales
            for this_line in line:
                this_line = re.sub(r'\$ +', '$', this_line)
                word = this_line.split()

                if is_sale(word):
                    # extract sale dictionary
                    sale = this_default_sale.copy()
                    sale.update(get_sale(word))
                    if sale != this_default_sale:
                        writer.writerow(sale)                        


if __name__ == '__main__':
    main()
