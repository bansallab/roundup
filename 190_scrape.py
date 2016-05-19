import csv
from urllib.request import Request, urlopen
import urllib.error
import dateutil.parser
from datetime import date
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util
 

default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/category/market-reports/'
strip_char = ';,. \n\t'
dash = b'\xe2\x80\x93'.decode()
start_page_num = 1


def get_sale_date(header):
    """Return the date of the sale."""

    date_string = re.split(b'\xe2\x80\x93'.decode(), header)[-1]
    sale_date = dateutil.parser.parse(date_string, fuzzy = True).date()
    if sale_date == date.today():
        sale_date = None

    return sale_date


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    if this_line == [] or this_line[-1] == '':
        return False

    is_not_succinct = len(this_line) > 2
    has_number = False
    for word in this_line:
        if is_number(word):
            has_number = True
            break
    last_word_number = re.search(r'[0-9]+', this_line[-1])
    
    return bool(is_not_succinct and has_number and not last_word_number)


def get_sale_location(sale_location):
    """Convert address strings into a list of address components."""

    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + r')$', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/]|cwt|he?a?d?|each|lbs?|per ?pair', '', string, flags = re.IGNORECASE)
        try:
            float(string)
            result = True
        except ValueError:
            result = False
    else:
        result = False

    return result


def get_sale(word):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    number_word = [idx for idx, val in enumerate(word) if is_number(val)]
    
    sale_location = get_sale_location(word[-1])
    sale = {
        'consignor_city': sale_location.pop(0).strip(strip_char).title()
        }
                
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    head_match = re.match(r'[0-9,]+', word[0])
    if not head_match:
        head_match = re.search(r'\([0-9,]+\)', word[0])
    if not head_match:
        head_match = re.search(dash + r'\s*[0-9,]$', word[0])
    if head_match:
        sale['cattle_head'] = re.sub(r'[^0-9]', '', head_match.group(0))
        cattle_string = word[0].replace(head_match.group(0), '').strip()

    else:
        try:
            cattle_string, head_string = re.split(b'\xe2\x80\x93'.decode(), word[0])
            try:
                int(head_string.replace(',',''))
                sale['cattle_head'] = head_string.replace(',','')
            except ValueError:
                cattle_string = cattle_string + '-' + head_string
        except ValueError:
            cattle_string = word[0].strip()

    cattle_string = cattle_string + ' ' + ' '.join(word[1:number_word[0]])

    weight_match = re.search(r'([0-9,.]+) ?lbs? *', cattle_string)
    if weight_match:
        sale['cattle_avg_weight'] = weight_match.group(1).replace(',','')
        cattle_string = cattle_string.replace(weight_match.group(),'')

    sale['cattle_cattle'] = cattle_string.strip(strip_char)

    price_string = ' '.join(word[number_word.pop():-1])
    
    if number_word:
        weight_string = word[number_word.pop()]
        weight_string = weight_string.replace('lbs','').strip(strip_char).replace(',', '')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass

    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?(each|per ?pair)', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)
        
    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line))
            writer.writerow(sale)


def main():            

    page_num = start_page_num
    while page_num:

        # Collect individual reports into a list
        request = Request(
            '{}{}page/{}/'.format(base_url, report_path, page_num),
            headers = scrape_util.url_header,
        )

        try:
            with urlopen(request) as io:
                soup = BeautifulSoup(io.read())
        except urllib.error.HTTPError:
            break

        content = soup.find('div', id='content')
        article_title = [article.find('h2') for article in content.find_all('article')]
        report = [title.find('a') for title in article_title]

        # Locate existing CSV files
        archive = scrape_util.ArchiveFolder(argv, prefix)

        # Write a CSV file for each report not in the archive
        for this_report in report:

            header = this_report.string

            cattle_clue = r'cows?|bulls?|calf|calves|yearlings?|steers?|holsteins?|pairs?|cattle'
            # Skip report if report describes sale of non-cattle
            if not re.search(cattle_clue, header, re.IGNORECASE):
                continue

            sale_date = get_sale_date(header)
            # if not sale_date:
            #     print(this_report['href'])
            #     date_string = input('date_string: ')
            #     sale_date = dateutil.parser.parse(date_string).date()
            io_name = archive.new_csv(sale_date)

            # Stop iteration if this report is already archived
            if not io_name:
               page_num = -1
               break

            # Initialize the default sale dictionary
            this_default_sale = default_sale.copy()
            this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                })

            request = Request(
                this_report['href'],
                headers = scrape_util.url_header,
            )

            with urlopen(request) as io:
                soup = BeautifulSoup(io.read(), 'html5lib')

            article = soup.find('article')
            table = article.find('table')
            line = []
            # List each line of the report
            if table:
                for tr in table.find_all('tr'):
                    this_line = []
                    for td in tr.find_all('td'):
                        if td.get_text().replace('\xa0',' ').strip() != '':
                            this_line.append(td.get_text().replace('\xa0',' ').strip())
                    line.append(this_line)

            else:
                div = article.find('div', class_ = 'entry fix')
                for p in div.find_all('p'):
                    txt = p.get_text().replace('\xa0',' ')
                    if txt.count(dash) < 2:
                        txt = re.split(r'\s{2,}', txt.replace('cwt ', 'cwt  '))
                    else:
                        txt = re.split(dash, txt)
                    txt = [string.strip() for string in txt]
                    line.append(txt)

            # Open a new CSV file and write each sale
            with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()
                write_sale(line, this_default_sale, writer)

        page_num += 1


if __name__ == '__main__':
    main()
