import csv
import requests
import re
import scrape_util
import dateutil.parser
from sys import argv
from bs4 import BeautifulSoup


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'custom/market-reports'


def post_data(soup, report_type=None, report_date=None, get=False):

    post_report_type = 'ctl00$LeftSidePlaceholder$ctl03$ddlMarketReportTypes'
    post_report_date = 'ctl00$LeftSidePlaceholder$ctl03$ddlMarketReportDate'
    post_get_report = 'ctl00$LeftSidePlaceholder$ctl03$btnGetReport'

    viewstate = soup.find('input', attrs={'id': '__VIEWSTATE'})
    validation = soup.find('input', attrs={'id': '__EVENTVALIDATION'})
    data = {
        post_report_type: report_type,
        post_report_date: report_date,
        post_get_report: 'Get Report' if get == True else None,
        '__VIEWSTATE': viewstate['value'],
        '__EVENTVALIDATION': validation['value'],
        }

    return {k: v for k, v in data.items() if v}


def get_sale(row, heading, price):
    """Convert the input into a dictionary, with keys matching
    the CSV column headers in the scrape_util module.
    """

    label = {label['class'][0]: label.get_text() for label in row.find_all('label')}
    sale = {
        'consignor_city': label['name'].split(',')[0],
        'consignor_state': label['name'].split(',')[1],
        'cattle_cattle': " ".join([heading, label['color'], label['desc']]),
        'cattle_avg_weight': label['weight'],
        price: label['value'],
        }
    sale = {k: v.strip() for k, v in sale.items() if v}

    return sale


def write_sale(report, this_default_sale, writer):
    """Extract sales from a list of report lines
    and write them to a CSV file."""

    if 'bred' in this_default_sale['sale_title'].lower():
        price = 'cattle_price'
    else:
        price = 'cattle_price_cwt'

    for item in report:
        heading = item.h2
        if heading:
            heading = heading.get_text()
        else:
            continue
        for row in item.find_all('div'):
            sale = this_default_sale.copy()
            sale.update(get_sale(row, heading, price))
            if sale != this_default_sale:
                writer.writerow(sale)


def main():

    session = requests.Session()
    session.headers.update(scrape_util.url_header)
    response = session.get(
        url=base_url + report_path,
        )
    soup = BeautifulSoup(response.content)
    div = soup.find('div', attrs={'id': 'marketReports'})
    report_type = div.find(
        'select',
        attrs={'id': re.compile('.*_ddlMarketReportTypes')}
        )
    report_type = {tag['value']: tag.get_text() for tag in report_type.find_all('option')}
    report_type.pop('-1')

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    for this_report_type in report_type:

        data = post_data(soup, this_report_type)
        response = session.post(
            base_url + report_path,
            data=data,
            headers={'Referer': base_url}
            )
        soup = BeautifulSoup(response.content)
        div = soup.find('div', attrs={'id': 'marketReports'})
        report_date = div.find(
            'select',
            attrs={'id': re.compile('.*_ddlMarketReportDate')}
            )
        report_date = [tag['value'] for tag in report_date.find_all('option')]
        report_date.remove('-1')

        for this_report_date in report_date:

            sale_date = dateutil.parser.parse(this_report_date)
            io_name = archive.new_csv(sale_date)

            # Stop iteration if this report is already archived
            if not io_name:
                continue

            data = post_data(soup, this_report_type, this_report_date, True)
            response = session.post(
                url=base_url + report_path,
                data=data,
                headers={'Referer': base_url}
                )
            soup = BeautifulSoup(response.content)
            this_report = soup.find_all('div', attrs={'class': 'item'})
            sale_head = soup.find('span', attrs={'id': re.compile('.*_lblHeadSold')})
            sale_head = re.match('Head Sold: (\d+)', sale_head.get_text()).group(1)

            # Initialize the default sale dictionary
            this_default_sale = default_sale.copy()
            this_default_sale.update({
                'sale_year': sale_date.year,
                'sale_month': sale_date.month,
                'sale_day': sale_date.day,
                'sale_head': sale_head,
                'sale_title': report_type[this_report_type],
                })

            # Open a new CSV file and write each sale
            with io_name.open('w', encoding='utf-8') as io:
                writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
                writer.writeheader()
                write_sale(this_report, this_default_sale, writer)


if __name__ == '__main__':
    main()
