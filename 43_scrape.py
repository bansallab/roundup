import csv
from urllib.request import Request, urlopen
import urllib.error
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
base_url += 'Markets/'
report_path = 'index.php'
strip_char = ';,. \n\t\\'


def is_number(string):
    string = re.sub(r'[^\w]', '', string)
    try:
        float(string)
        return True
    except ValueError:
        return False
    

def is_sale(word):

#    result = False;
#    if len(word) == 5:
#        number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))
#        if number_word == [0, 2, 3]:
#            result = True
    has_price = False
    is_not_succinct = len(word) > 3
    if is_not_succinct:
        has_price = re.search(r'\$[0-9,]+\.[0-9]{2}', ''.join(word[-2]))
   
    return bool(has_price)


def get_sale_date(string):
    date_string = string.get_text()
    sale_date = parser.parse(date_string)
    
    return sale_date


def get_sale_head(line):

    sale_head = None
    for this_line in line:
        match = re.search(r'receipts:\s*([0-9,]+)', this_line, re.IGNORECASE)
        if match:
            sale_head = match.group(1).replace(',','')
            break
        second_match = re.search(r'receipts\sof\s([0-9,]+)\s?(head|hd)', this_line, re.IGNORECASE)
        if second_match:
            sale_head = second_match.group(1).replace(',','')
            break

    return sale_head
    

def get_sale_location(string):
    
    if ',' in string:
        sale_location = string.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', string)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [string]

    return sale_location


def get_sale(word, price_type):

    if '/' in word[0]:
        match = re.search(r'/([\s0-9]+)(.*)', ' '.join(word[0:2]))
        if match:
            word[0] = match.group(1)
            word[1] = match.group(2)
    
    sale_location = get_sale_location(word.pop())
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'cattle_head': re.sub(r'[^0-9.]', '', word.pop(0)),
        }
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    price_string = re.sub(r'[^0-9.]', '', word.pop())
    if price_type=='HD':
        sale['cattle_price'] = price_string
    elif price_type=='WT':
        sale['cattle_price_cwt'] = price_string

    cattle_avg_weight = re.sub(r'[^0-9.]', '', word.pop()) ## can ditch sub?
    cattle_string = ' '.join(word).strip(strip_char)
    if not cattle_avg_weight:
        match = re.search(r'\s([0-9,]+)$', cattle_string)
        if match:
            cattle_avg_weight = match.group(1)
            cattle_string = cattle_string.replace(match.group(0), '')
    sale['cattle_avg_weight'] = re.sub(r'[^0-9]', '', cattle_avg_weight)
    sale['cattle_cattle'] = re.sub(r'\s', ' ', cattle_string)
                        
    sale = {k: v.strip() for k, v in sale.items() if v.strip()}
    
    return sale


def main():
    
    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers=scrape_util.url_header,
        )
    soup = BeautifulSoup(urlopen(request).read())
    div = soup.find('div', attrs = {'id': 'content'})
    report = list(list(td for td in tr.find_all('td')) for tr in div.table.find_all('tr') if re.search(r'market report', tr.get_text(), re.IGNORECASE))

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        # sale defaults
        sale_date = get_sale_date(this_report[1])
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # skip if already archived
        io_name = archive.new_csv(sale_date)
        
        if not io_name:
            continue

        # query this_report for sale data
        try:
            request = Request(
                base_url + this_report[0].a['href'],
                headers = scrape_util.url_header,
                )
            soup = BeautifulSoup(urlopen(request).read())
            div = soup.find('div', attrs = {'id': 'content'})
            details = div.table.find_all('tr')[2].find_all('td')[1]
        except urllib.error.HTTPError:
            print('HTTP error: {}'.format(request.full_url))
            continue

        if details.pre:
            line = list(line.replace(' ', '\xa0') for line in details.pre.get_text().splitlines())
        elif details.br:
            string_text = details.br.get_text('|||')
            line = string_text.split('|||')
        else:
            line = []

        p_tag = details.find_all('p')
        for p in p_tag:
            if p.br:
                txt = p.get_text('|||')
                line_to_add = txt.split('|||')
                line += line_to_add
            else:
                line.append(p.get_text())

        sale_head = get_sale_head(line)
        this_default_sale.update({
            'sale_head': sale_head,
            })
        
        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()

            # extract & write sale dictionary
            price_type = None
            for this_line in line:
                word = [this_word for this_word in re.split(r'\xa0|\r\n', this_line) if this_word]
                match = re.search(r'\s{4,}(WT|HD)', this_line)
                if match:
                    price_type = match.group(1)
                if price_type and is_sale(word):
                    sale = this_default_sale.copy()
                    sale.update(get_sale(word, price_type))
                    if sale != this_default_sale:
                        writer.writerow(sale)


if __name__ == '__main__':
    main()
