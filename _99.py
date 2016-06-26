import csv
from urllib.request import Request, urlopen
import dateutil.parser
import re
from sys import argv
from bs4 import BeautifulSoup
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'market-reports.html'
strip_char = ';,. \n\t\xa0'


def is_number(string):
    has_string = re.search(r'[1-9]',string)
    return bool(has_string)


def get_sale_date(date_string):
    """Return the date of the livestock sale."""

    sale_date = dateutil.parser.parse(date_string, fuzzy=True)

    return sale_date


def is_heading(this_line):

    has_name = re.search(r'Feeder|Fat', str(this_line))
    not_sum = '/' not in str(this_line)

    return bool(has_name and not_sum)


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    has_location = len(this_line) > 3
    has_price = re.search(r'[0-9]+', str(this_line))
    combin = re.search(r'-', str(this_line))

    return has_location and bool(has_price) and not bool(combin)


def get_location(location):
    if "," in location:
        location = location.split(",")
        city = location[0]
        state = location[1].split()[-1]
    else:
        city = location
        state = ""
    return [city,state]


def get_sale(this_line, cattle):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    sale = {}
    location_list = get_location(this_line[0])

    sale['consignor_city'] = location_list.pop(0).title()
    sale['consignor_state'] = location_list.pop()

    number_word = [idx for idx, val in enumerate(this_line) if is_number(val)]

    weight_string = this_line[number_word[0]]
    sale['cattle_avg_weight'] = re.sub(r'[^0-9]', '', weight_string)

    price_string = this_line[number_word[1]]
    sale['cattle_price_cwt'] = re.sub(r'[^0-9.]', '', price_string)

    if len(this_line) == 4:
        cattle_string = this_line[1] + ' ' + cattle
    elif len(this_line) == 5:
        cattle_string = ' '.join(this_line[1:3]) + ' ' + cattle
    elif len(this_line) == 3:
        cattle_string = cattle
    sale['cattle_cattle'] = cattle_string

    sale = {k: v for k, v in sale.items() if v}

    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    for this_line in line:
        if is_heading(this_line):
            cattle = this_line[0]
        elif is_sale(this_line):
            sale = this_default_sale.copy()
            sale.update(get_sale(this_line, cattle))
            writer.writerow(sale)


def main():

    # Get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    report = soup.find_all('a', {'class': 'button'})

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Write a CSV file for each report not in the archive
    for this_report in report:

        sale_date = get_sale_date(this_report.get_text())
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            continue

        link = this_report['href']
        request = Request(
            base_url + link,
            headers = scrape_util.url_header,
            )
        
        with urlopen(request) as io:
            soup = BeautifulSoup(io.read(), 'lxml')

        cattle_base = link.split("-")[0].title()
        div = soup.find_all('div', attrs={'class': 'txt'})
        table = []
        for this_div in div:
            cattle = ''
            if this_div.h3:
                cattle = this_div.find_all('h3')[-1]
            elif this_div.h2:
                cattle = this_div.find_all('h2')[-1]
            if cattle:
                cattle = ' '.join([cattle_base, cattle.get_text().strip()])
            if this_div.table:
                table.append((cattle, this_div.table))

        line = []
        for this_table in table:
            line.append(this_table[0])
            for tr in this_table[1].find_all('tr'):
                line.append([td.get_text().strip() for td in tr.find_all('td')])

        # cattle_list = soup.find_all("h2") + soup.find_all("h3")
        # cattle_list = [
        #     cattle + ' ' + this_cattle.get_text() for this_cattle in cattle_list
        #     if this_cattle.get_text()
        #     ]
        # cattle_list = cattle_list[1:]

        # tables = soup.find_all("table")
        
        # Initialize the default sale dictionary
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # for idx, this_cattle in enumerate(cattle_list):
        #     if "/" in this_cattle:
        #         del cattle_list[idx]
        #         del tables[idx]
        #     elif (not this_cattle) or ("Sale" in this_cattle) or is_number(this_cattle):
        #         del cattle_list[idx]
        #     elif is_number(this_cattle):
        #         del cattle_list[idx]

        # line = []
        # for idx, this_cattle in enumerate(cattle_list):
        #     line.append([this_cattle])
        #     table_tr = tables[idx].findAll("tr")
        #     for this_table_tr in table_tr:
        #         table_td = this_table_tr.findAll("td")
        #         table_col = [td.get_text().strip() for td in table_td]
        #         line.append(table_col)

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
