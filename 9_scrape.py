import csv
from urllib.request import Request, urlopen
import urllib.error
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t'
report_path = '/index.cfm'


def is_sale(this_line):
   return re.search(r'\s\$\s', this_line)


def get_sale_date(this_report):

    text = this_report.get_text()
    match = re.search(r'[0-9]+[-/][0-9]+[-/][0-9]+', text)
    if match:
        date_string = match.group(0)
        sale_date = parser.parse(date_string)
    elif 'EMCC Catalog' in text:
        sale_date = None
    else:
        date_string = text
        sale_date = parser.parse(date_string)        
    
    return sale_date


def get_sale_head(line):

    
    for this_line in line:
        if re.search(r'receipts?', this_line, re.IGNORECASE):
            match = re.search(r'([0-9]+)', this_line)
            if match:
                return match.group(1)
            break
        


def get_sale_location(word):
    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', sale_location)
        sale_location = [match.group(1), match.group(2)]

    return sale_location
    

def get_sale(word):

    number_word = [idx for idx in range(len(word)) if scrape_util.is_number(word[idx])]
    if number_word == [0, 2, 3, 5]:
        sale_location = get_sale_location(word[6:])
        sale = {
            'consignor_city': sale_location[0].strip(strip_char).title(),
            'consignor_state': sale_location[1].strip(strip_char),
            'cattle_head': word[0].strip(strip_char),
            'cattle_cattle': word[1].strip(strip_char),
            'cattle_avg_weight': word[2].strip(strip_char).replace(',', ''),
            'cattle_price_cwt': word[3].strip(strip_char).replace(',', ''),
            }
    elif number_word == [0, 1, 2, 4]:
        sale_location = get_sale_location(word[5:])
        sale = {
            'consignor_city': sale_location[0].strip(strip_char).title(),
            'consignor_state': sale_location[1].strip(strip_char),
            'cattle_head': word[0].strip(strip_char),
            'cattle_avg_weight': word[1].strip(strip_char).replace(',', ''),
            'cattle_price_cwt': word[2].strip(strip_char).replace(',', ''),
            }
    elif number_word[1] > 3:
        sale_location = get_sale_location(word[3:number_word[1]])
        sale = {
            'consignor_city': sale_location[0].strip(strip_char).title(),
            'consignor_state': sale_location[1].strip(strip_char),
            'cattle_head': word[0].strip(strip_char),
            'cattle_cattle': ' '.join(word[1:3]).strip(strip_char),
            'cattle_avg_weight': word[number_word[1]].strip(strip_char).replace(',', ''),
            'cattle_price_cwt': word[number_word[2]].strip(strip_char).replace(',', ''),
            }
    else:
        raise Exception
    
    sale = {k: v for k, v in sale.items() if v}
    
    return sale


def main():

   # get URLs for all reports
   request = Request(
       base_url + report_path,
       headers = scrape_util.url_header,
       )
   with urlopen(request) as io:
       soup = BeautifulSoup(io.read())
   ul = soup.find_all('ul', attrs = {'class' : 'depth2' })
   report_list = list(
       this_ul for this_ul in ul
       if any(
           this_sibling.name and 'Market Report' in this_sibling.get_text() for this_sibling in this_ul.previous_siblings
           if this_sibling
           )
       )
   report = [li.a for this_report_list in report_list for li in this_report_list.find_all('li')]

   # Identify existing reports
   archive = scrape_util.ArchiveFolder(argv, prefix)

   # write csv file for each historical report
   for this_report in report:

       # sale defaults
       sale_date = get_sale_date(this_report)
       if not sale_date:
           # ignores otherwise fine data from a single report that is atypically formated
           continue
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
       request = Request(
           base_url + this_report['href'],
           headers = scrape_util.url_header,
           )
       try:
           with urlopen(request) as io:
               soup = BeautifulSoup(io.read())
       except urllib.error.HTTPError:
           print('HTTP error: {}'.format(url))
           continue
       line = [this_line for this_line in soup.stripped_strings]

       sale_head = get_sale_head(line)
       this_default_sale.update({
           'sale_head': sale_head,
           })
       
       # open csv file and write header
       with io_name.open('w', encoding='utf-8') as io:
           writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
           writer.writeheader()
   #        n_sale = 0

           # sales
           for this_line in line:
               if is_sale(this_line):
   #                n_sale += 1
                   # extract sale dictionary
                   word = this_line.split()
                   sale = this_default_sale.copy()
                   sale.update(get_sale(word))
                   if sale != this_default_sale:
                       writer.writerow(sale)

   #        if n_sale == 0:
   #            print('No sales found: {}'.format(url))


if __name__ == '__main__':
    main()
