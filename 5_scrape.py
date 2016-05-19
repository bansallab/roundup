import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import date
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'sale_reports/{}.offset'


def get_sale_date(date_string):
    sale_date = parser.parse(date_string).date()
    if sale_date >= date.today():
        sale_date = None
    return sale_date


def get_sale(text):
    # some sales are reported as individual lots without consignor
    if re.match(r'lot.*\u2014a high selling', text, re.IGNORECASE):
        lot = re.search(r'\u2014(.*), sold to (.*) from (.*), for \$?(.*).', text)
        buyer_location = lot.group(3).split(', ')
        sale = {
            'cattle_cattle': lot.group(1).strip(', '),
            'buyer_name': lot.group(2).strip(', '),
            'buyer_city': buyer_location[0].strip(', '),
            'buyer_state': buyer_location[1].strip(', '),
            }
        try:
            sale.update({'cattle_price': float(lot.group(4).replace(',', ''))})
        except ValueError:
            print('ValueError while trying float on: ', lot.group(4).replace(',', ''))
        sale_list = [sale]

    # some sales are reported as individual lots
    elif re.match(r'lot', text, re.IGNORECASE):
        lot = re.search(r'\u2014(.*) from (.*), sold (.*) to (.*) from (.*), for \$?(.*).', text)
        consignor_location = lot.group(2).split(', ')
        buyer_location = lot.group(5).split(', ')
        sale = {
            'consignor_name': lot.group(1).strip(', '),
            'consignor_city': consignor_location[0].strip(', '),
            'consignor_state': consignor_location[1].strip(', '),
            'cattle_cattle': lot.group(3).strip(', '),
            'buyer_name': lot.group(4).strip(', '),
            'buyer_city': buyer_location[0].strip(', '),
            'buyer_state': buyer_location[1].strip(', '),
            }
        try:
            sale.update({'cattle_price': float(lot.group(6).replace(',', ''))})
        except ValueError:
            print('ValueError while trying float on: ', lot.group(4).replace(',', ''))
        sale_list = [sale]
            
    # some sales are reported as volume sales
    elif re.match(r'volume', text, re.IGNORECASE):
        buyer_text = re.sub(r'^.* made by (.*)', r'\1', text)
        buyer = re.finditer(r'(?: and )?([^,]+) from ([^,]*), ([^,]*)[,\.]', buyer_text, re.IGNORECASE)
        sale_list = []
        for this_buyer in buyer:
            sale_list.append({
                'cattle_cattle': 'volume',
                'buyer_name': this_buyer.group(1).strip(', '),
                'buyer_city': this_buyer.group(2).strip(', '),
                'buyer_state': this_buyer.group(3).strip(', '),
                })
    else:
        raise Exception('Unspecified sale type!')

    return sale_list


class Report(object):
    
    def __init__(self):
        self.offset = 0
    
    def __iter__(self):
        return self

    def __next__(self):
        # Reports are handled individually by incrementing the offset in the url
        # and taking the first 'vastQueryResulter' div
        request = Request(
            base_url + report_path.format(self.offset),
            headers=scrape_util.url_header,
            )
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read())
        this_report = soup.div
        this_report = this_report.find_next(attrs = {'class' : 'vastQueryResultery'})
        if bool(this_report):
            self.offset += 1
            return this_report
        else:
            raise StopIteration


def main():

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Turn each report into a csv file
    for this_report in Report():

        # gather venue information from the <h6> tag        
        venue = this_report.h6.get_text().splitlines()
        location = [selection for selection in venue if 'location:' in selection]

        if len(location) == 0:
            location = ''
        else:
            location = location[0]

        date_str = [selection for selection in venue if 'date of sale:' in selection]

        if len(date_str) == 0:
            date_str = ''
        else:
            date_str = re.sub(r'date of sale: (.*)', r'\1', date_str[0], re.IGNORECASE)
            sale_date = get_sale_date(date_str)

        if not sale_date:
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_title': this_report.h2.get_text(),
            'sale_city': re.sub(r'location: ([^,]*),.*', r'\1', location, re.IGNORECASE),
            'sale_state': re.sub(r'location: [^,]*, (.*)', r'\1', location, re.IGNORECASE),
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # step through each sale by incrementing through <p> tags
        line = this_report.find_all('p')

        if len(line) > 0:

            io_name = archive.new_csv(sale_date, title = this_default_sale['sale_title'])
            if not io_name:
                break

            with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()

                for this_line in line:
                    text = this_line.get_text()
                    sale = this_default_sale.copy()
                    for this_sale in  get_sale(text):
                        sale.update(this_sale)
                        writer.writerow(sale)


if __name__ == '__main__':
    main()
