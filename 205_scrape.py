import csv
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path_1 = 'market_report/more'
report_path_2 = 'market_report/report/?date='
strip_char = ';,. \n\t'


def get_sale_date(link):

    """Return the date of the livestock sale."""

    sale_date = dateutil.parser.parse(link, fuzzy=True)

    return sale_date


def get_sale_head(table):
    """Return the head of the livestock sale."""

    texts = [text for text in table.stripped_strings]
    for text in texts:
        if re.search(r'cattle sold', text, re.IGNORECASE):
            match = re.search(r'([0-9]+)', text)
            if match:
                return match.group(1)
            break
            

def is_sale(line):
    """Determine whether a given line describes a sale of cattle."""

    return len(line) == 5


def is_number(string):
    """Test whether a string is numeric."""

    string = re.sub(r'\$|,', '', string, flags=re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_sale(line):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    # Seperate line into numerical data and cattle_cattle
    cattle_cattle = line[1].split()
    cattle_cattle[1:] = [' '.join(cattle_cattle[1:])]

    sale = {
        'consignor_city': line[0],
        'cattle_head': cattle_cattle[0],
        'cattle_cattle': cattle_cattle[1],
        }

    if is_number(line[2]):
        sale['cattle_avg_weight'] = line[2]
    if is_number(line[3]):
        sale['cattle_price_cwt'] = line[3]
    if is_number(line[4]):
        sale['cattle_price'] = line[4]

    sale = {k: v for k, v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line))
            writer.writerow(sale)


def main():
    # Get URLs for all reports
    request = Request(
        base_url + report_path_1,
        headers = scrape_util.url_header,
        )

    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())

    h2 = soup.h2
    sib = list(sib for sib in h2.next_siblings)
    report = []

    # Finding the date links
    for this_line in sib:
        if isinstance(this_line,str):
            if 'sheep' in this_line.lower():
                report.pop()
        else:
            if this_line.string:
                if re.search(r'[0-9]{,2}/[0-9]{,2}/[0-9]{4}',this_line.string):
                    report.append(this_line.string)

    if report:
        report.pop()

    archive = scrape_util.ArchiveFolder(argv, prefix)

    for this_report in report:

        # Set the sale_date for .csv filenames
        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)

        # Duplicate checking
        if not io_name:
            continue

        # Pull the link request
        request = Request(
            base_url + report_path_2 + sale_date.strftime('%Y-%m-%d'),
            headers = scrape_util.url_header,
            )
        try:
            with urlopen(request) as io:
                soup = BeautifulSoup(io.read())
        except HTTPError:
            continue

        # Update sale with date
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
        })

        # Create orderly list by finding all table rows
        tables = soup.findChildren('table')
        sale_head = get_sale_head(tables[1])
        this_default_sale.update({
            'sale_head': sale_head,
        })
        my_table = tables[-1]
        rows = my_table.findChildren('tr')
        table_rows = []
        for row in rows:
            table_cols = [td.get_text().replace('\x97', ' ').strip() for td in row.findAll('td')]
            table_rows.append(table_cols)

        # Do not need zeroth element
        table_rows.pop(0)

        line = table_rows

        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
