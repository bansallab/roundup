import csv
from itertools import groupby
from selenium import webdriver
from time import sleep
import dateutil.parser
import re
from sys import argv
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market-report.html'
strip_char = ';,. \n\t'
clean_char = re.compile(r'\s*\n+\s*')
head_pattern = re.compile(r'([0-9]+) head of cattle', re.IGNORECASE)
date_pattern = re.compile(r'sale date:(.*)', re.IGNORECASE)
price_pattern = re.compile('\.\d{2}$')
PIXEL_GAP = 22
SECOND_COLUMN = 500


def get_sale_date(link):
    """Return the date of the livestock sale."""

    sale_date = dateutil.parser.parse(link, fuzzy = True)
        
    return sale_date


def is_sale(line):
    is_upper = line[0].isupper()
    right_length = 1 < len(line) < 4
    has_price = price_pattern.search(line[-1])
    ranges = ' to ' in line[-1]
    return (not is_upper) and right_length and bool(has_price) and (not ranges)


def is_number(string):
    """Test whether a string is numeric. Ignoring units like 'cwt' and 'hd'."""

    string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False
    

def get_sale(line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    text = re.sub('(' + scrape_util.state + ')' + r'\s(\d)', r'\1, \2', line[0])
    text = text.split(',')

#    this_line = re.sub('(' + scrape_util.state + ')' + r'\s(\d)', r'\1, \2', this_line)
#    new_line = this_line.split('\n', maxsplit = 1)
#    data = new_line[0].split(',')

#    numbers = new_line[-1].replace('\n', ' ')
    types = text.pop().split()
    if not types:
        types = text.pop().split()

    if is_number(types[0]):
        cattle_head = types.pop(0)
    else:
        cattle_head = ''

    sale = ({
        'consignor_state': text.pop().strip(),
        'consignor_city': text.pop().strip(),
        'consignor_name': ''.join(text).strip(),
        'cattle_head': cattle_head,
        'cattle_cattle': ' '.join(types),
        })

    if len(line) == 3 and '#' in line[-2]:
        sale.update({
            'cattle_avg_weight': line[-2].strip('#').replace(',', ''),
            'cattle_price_cwt': line[-1].replace(',', '')
            })
    else:
        sale['cattle_price'] = line[-1].replace(',', '').strip()
                
    sale = {k:re.sub(clean_char, ' ', v).strip() for k, v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line))
            writer.writerow(sale)


def main():

    archive = scrape_util.ArchiveFolder(argv, prefix)

    # request = Request(
    #     base_url,
    #     headers = scrape_util.url_header,
    #     )

    # with urlopen(request) as io:
    #     soup = BeautifulSoup(io.read())

    # report = [soup]

    report = [None]

    for this_report in report:

        # Extract table from table-like collection of div elements.
        phantom = webdriver.PhantomJS()
        phantom.get(base_url + report_path)
        sleep(1)

        content = []
        for div in phantom.find_elements_by_css_selector("div.txt"):
            for p in div.find_elements_by_tag_name('p'):
                y = p.location['y']
                x = p.location['x']
                if x > SECOND_COLUMN:
                    y += PIXEL_GAP / 2
                for text in p.text.splitlines():
                    content.append([y, x, text])
                    y += PIXEL_GAP
        content.sort(key = lambda x: x[:2])
        y = 0
        last_y = content[0][0]
        for row in content:
            this_y = row[0]
            if (this_y - last_y) >= PIXEL_GAP:
                last_y = this_y
                y += 1
            row[0] = y
        line = []
        for _, g in groupby(content, key=lambda text: text[0]):
            this_line = sorted(list(g), key=lambda text: text[1])
            line.append([text[-1] for text in this_line])
            
        for this_line in line:
            match = date_pattern.search(' '.join(this_line))
            if match:
                sale_date = get_sale_date(match.group(1))
                break

        io_name = archive.new_csv(sale_date)
        if not io_name:
            break

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day
            })

        for this_line in line:
            match = head_pattern.search(' '.join(this_line))
            if match:
                this_default_sale['sale_head'] = match.group(1)
                break

        with io_name.open('w') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
