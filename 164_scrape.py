import csv
from urllib.request import Request, urlopen
import re
from datetime import date
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
temp_raw = scrape_util.ReportRaw(argv, prefix)
report_path = 'index.php?option=com_content&view=article&id=251&Itemid=575'
strip_char = ';,. \n\t'


def get_sale_date(date_string):
    """Return the date of the sale."""

    sale_date = dateutil.parser.parse(date_string, fuzzy = True)

    return sale_date


def get_sale_day(date_string, year):
    """Return the date of the sale."""

    date_string = date_string.replace(str(year), '')
    match = re.search(r'([0-9]+)', date_string)
    if match:
        sale_day = int(match.group(1))

    return sale_day


def is_heading(word):
    """Determine whether a given line is a section header
    that describes subsequent lines of a report.
    """

    cattle_clue = r'(bulls?|steers?|strs?|cows?|heifers?|hfrs?|calf|calves|pairs?|cattle|weighups?|yrlgs?)'
    is_not_succinct = len(word) > 1
    has_cattle = False
    has_number = False
    for this_word in word:
        if re.search(cattle_clue, this_word, re.IGNORECASE):
            has_cattle = True
            break
    for this_word in word:
        if re.search(r'[0-9]', this_word):
            has_number = True
            break

    return bool(is_not_succinct and has_cattle and not has_number)


def is_sale(word):
    """Determine whether a given line describes a sale of cattle."""

    is_not_succinct = len(word) > 2
    has_price = False
    for this_word in word:
        if re.search(r'[0-9,]+\.[0-9]{2}', this_word):
            has_price = True
            break

    return bool(has_price and is_not_succinct)


def is_number(string):
    """Test whether a string is number-ish. Ignoring units like 'cwt' and 'hd'."""

    if string:
        string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
        try:
            float(string)
            result = True
        except ValueError:
            result = False
    else:
        result = False

    return result


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
    sale_location = re.sub(r'\(.*?\)$', '', sale_location)
    match = re.search(r'(.*?),?(' + scrape_util.state + r')$', sale_location, re.IGNORECASE)
    if match:
        sale_location = [match.group(1), match.group(2)]
    else:
        sale_location = [sale_location]

    return sale_location


def get_sale(word, consignor_info, price_key):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    if len(word)==2:
        match = re.search(r'\b([0-9]+)$', word[0])
        if match:
            word[0:1] = [word[0].replace(match.group(1), ''), match.group(1)]
            
    number_word = [idx for idx, val in enumerate(word) if is_number(val)]

    name_location = consignor_info.split(',')
    consignor_name = name_location.pop(0)

    if name_location:
        if re.search(r'&',name_location[0]):
            consignor_name = consignor_name.strip() + ',' + name_location.pop(0)

    sale = {
        'consignor_name': consignor_name.strip(strip_char).title(),
        }

    if name_location:
        sale_location = get_sale_location([','.join(name_location)])
        sale['consignor_city'] = sale_location.pop(0).strip(strip_char).title()
        if sale_location:
            sale['consignor_state'] = sale_location.pop().strip(strip_char)

    cattle_string = word[number_word[0]-1]
    head_match = re.match(r'([0-9,]+)', cattle_string)
    if head_match:
        head_string = head_match.group(1).replace(',','')
        try:
            int(head_string)
            sale['cattle_head'] = head_string
        except ValueError:
            pass
        cattle_string = cattle_string.replace(head_match.group(),'')

    sale['cattle_cattle'] = cattle_string.strip(strip_char)

    weight_string = word[number_word[0]].strip(strip_char).replace(',', '')
    try:
        float(weight_string)
        sale['cattle_avg_weight'] = weight_string
    except ValueError:
        pass

    price_string = word[number_word[1]]
    match = re.search(r'([0-9,.]+)', price_string, re.IGNORECASE)
    if match:
        sale[price_key] = match.group(1).replace(',', '').strip(strip_char)

    sale = {k:v.strip() for k,v in sale.items() if v.strip()}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    consignor_info = ''
    price_key = 'cattle_price_cwt'
    exist_sale = []

    for this_line in line:
        word = re.split('\s{2,}', this_line)

        if is_heading(word):
            cattle_clue = word[0]
            price_clue = word[-1]
            if re.search(r'cwt', price_clue, re.IGNORECASE):
                price_key = 'cattle_price_cwt'
            elif re.search(r'pr|hd', price_clue, re.IGNORECASE):
                price_key = 'cattle_price'
            else:
                if re.search(r'bred|pair', cattle_clue, re.IGNORECASE):
                    price_key = 'cattle_price'
                else:
                    price_key = 'cattle_price_cwt'
        elif is_sale(word):
            if word[0]=='':
                if re.match(r'[0-9]+', word[1]):
                    word.pop(0)
                    exist_sale.append(word)
                else:
                    word.pop(0)
                    if re.match(r',', word[0]) or re.search(r',$', consignor_info):
                        consignor_info = consignor_info + word[0]
                    else:
                        consignor_info = consignor_info + ',' + word[0]
                    exist_sale.append(word)
            else:
                for this_sale in exist_sale:
                    sale = this_default_sale.copy()
                    sale.update(get_sale(this_sale, consignor_info, price_key))
                    writer.writerow(sale)
                exist_sale.clear()

                consignor_info = word.pop(0)
                exist_sale.append(word)
                
    for this_sale in exist_sale:
        sale = this_default_sale.copy()
        sale.update(get_sale(this_sale, consignor_info, price_key))
        writer.writerow(sale)


def main():

    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )

    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')

    report = soup.find('div', attrs={'class': 'module'}).find_all('a')

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    for this_report in report:

        # create temporary text file from downloaded pdf
        request = Request(
            this_report['href'].replace(' ', '%20'),
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        exit_value = system(scrape_util.pdftotext.format(str(temp_raw)))
        if exit_value != 0:
            print('Failure convert PDF in {}.'.format(prefix))
            continue

        # read sale text into line list
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r', errors = 'ignore') as io:
            line = list(this_line.strip('\n') for this_line in io if this_line.strip())
        temp_raw.clean()

        sale_date = get_sale_date(line[0])

        io_name = archive.new_csv(sale_date)
        if not io_name:
            break

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()
                write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
