import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
import datetime
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market%20reports.htm'
strip_char = '$;,. \xa0\r\n\t'


def is_date(this_line):
    
    date_clue = '(MONDAY?|TUESDAY?|WEDNESDAY?|THURSDAY?|FRIDAY?)'
    has_date = re.search(date_clue, this_line[0],re.IGNORECASE)
    
    return bool(has_date)


def get_sale_date(line):
    """Return the date of the livestock sale."""

    today = datetime.date.today()
    year = today.year
    line = line.lower().replace('janaury', 'january')
    if str(year) in line:
        date_string = line.strip()
    else:
        date_string = line.strip() + ' ' + str(year)
    sale_date = dateutil.parser.parse(date_string, fuzzy=True)
    sale_date = sale_date.date()
    if sale_date > today:
        sale_date = sale_date.replace(year=(sale_date.year - 1))
    
    return sale_date


def get_sale_head(line):

    sale_head = re.search(r'\d+', line).group(0)

    return sale_head


def is_heading(this_line):
    """Determine whether a given line is a section header 
    that describes subsequent lines of a report.
    """
    cattle_clue = '(BRED?|COW?|BRED?|HEIFER?|BULL?|HEIFERETTE?|PAIRS?|CALF?|)'
    has_cattle = re.search(cattle_clue, str(this_line), re.IGNORECASE)
    is_succinct = len(this_line) < 3
    
    return bool(has_cattle and is_succinct)
    

def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_price = re.search(r'[0-9]+\.[0-9]{2}', str(this_line))
    is_not_succinct = len(this_line) > 3
    
    return bool(has_price and is_not_succinct)


def is_number(string):

    string = re.sub(r'\$|[,-/]|cw?t?|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale_location(sale_location):
    """Convert address strings into a list of address components."""

    sale_location = re.sub(r'\r|\n|\t', '', sale_location)
    city = ''
    state = ''
    if '[' in sale_location:
        name_stop = sale_location.index('[')
        name = sale_location[:name_stop]
        location = sale_location[name_stop + 1:]
        match = re.search(r'(.*?)(' + scrape_util.state + ')', location)
        if ']' in location:
            if match:
                city = match.group(1)
                state = match.group(2)
            else:
                city = location.strip(']')
        elif ']' not in sale_location and match:
            city = match.group(1)
            state = match.group(2)
    else:
        name = sale_location

    return [name, city, state]


def get_sale(this_line, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """
    sale_location = get_sale_location(this_line.pop(0))
    
    sale = {
        'consignor_name': sale_location.pop(0).strip(strip_char),
        'consignor_city': sale_location.pop(0).strip(strip_char).title(),
        'consignor_state': sale_location.pop(0).strip(strip_char),
        }

    sale['cattle_head'] = this_line.pop(0)
    cattle_string = this_line.pop(0)
    if not is_number(cattle_string):
        weight_string = this_line.pop(0)
        sale['cattle_cattle'] = cattle + ' ' + cattle_string
    else:
        weight_string = cattle_string
        sale['cattle_cattle'] = cattle

    sale['cattle_avg_weight'] = weight_string.replace(',', '')

    if re.search('h', this_line[-1], re.IGNORECASE):
        price_field = 'cattle_price'
    else:
        price_field = 'cattle_price_cwt'
    price_string = this_line[-1].replace(',', '').strip(strip_char)
    sale[price_field] = price_string
   
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    for this_line in line:
        this_line = [td.get_text().strip(strip_char) for td in this_line.find_all('td') if td.get_text().strip(strip_char)]
        if is_heading(this_line):
            cattle = ' '.join(this_line)
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line, cattle))
            writer.writerow(sale)


def main():            
    
    # Get URLs for all reports
    request = Request(
        base_url + report_path,
        headers=scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'html.parser')
    table = soup.find('td', attrs={'class': 'style9'}).find('table')
    report = table.find_all('table')

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # report = [tr.get_text().strip(strip_char) for tr in soup.find_all('tr')]
    # report = report[2:]
    #
    # line = []
    # date = []
    # for i in range(len(report)):
    #     this_line = report[i].split()
    #     try:
    #         if is_date(this_line):
    #             date.append(i)
    #     except:
    #         pass
    #     line.append(this_line)
    #
    # report = []
    # count = 1
    # n = len(date)
    # while count < n:
    #     report.append(line[:date[count]])
    #     count = count + 1
    # report.append(line[date[count-1]:])
    
    for this_report in report:

        tr = this_report.find_all('tr')
        header = tr.pop(0)
        header = header.find_all('td')

        sale_date = get_sale_date(header[0].get_text())

        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        sale_head = ' '.join([tag.get_text().strip() for tag in header[1:]])
        sale_head = get_sale_head(sale_head)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(tr, this_default_sale, writer)


if __name__ == '__main__':
    main()
