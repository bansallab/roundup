import csv
from itertools import groupby
from sys import argv
import sys
from os import system
from time import sleep
import dateutil.parser
import re
from urllib.request import urlretrieve
from selenium import webdriver
#from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = '/#!marketreport/cjg9'
PIXEL_GAP = 20
#DCAP = dict(DesiredCapabilities.PHANTOMJS)
#DCAP['phantomjs.page.settings.userAgent'] = scrape_util.url_header['user-agent']
temp_raw = scrape_util.ReportRaw(argv, prefix, suffix='jpg')


def get_sale_date(line):

    date_pattern = re.compile(r'[0-9]+/[0-9]+/[0-9]+')
    match = False
    while not match:
        date_string = ' '.join(line.pop(0))
        match = date_pattern.search(date_string)
    sale_date = dateutil.parser.parse(match.group(0))

    return sale_date.date()


def is_sale(this_line):
    return sum(1 for v in this_line if v.strip()) == 4


def is_heading(this_line):
    cattle_clue = ['strs', 'steers', 'heifers', 'cows', 'bulls', 'heiferettes', 'hfrs', 'hfrette']
    return this_line[0].lower().strip() in cattle_clue


def get_sale(word, cattle):

    sale = {
        'consignor_city': word[0].title(),
        'cattle_cattle': ' '.join([cattle, word[1]]),
        'cattle_avg_weight': word[2],
        }

    price_string = word[3]
    if 'head' in price_string.lower():
        sale['cattle_price'] = re.sub(r'[^0-9\.]', '', word[3])
    else:
        sale['cattle_price_cwt'] = word[3]

    if 'horses' in sale['cattle_cattle'].lower():
        sale = {}
    else:
        sale = {k: v.strip() for k, v in sale.items() if v.strip()}

    return sale


def write_sale(line, default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""

    cattle = None
    for this_line in line:
        if len(this_line) == 1 and re.search(r'\d+\.\d+\s*$', this_line[0]):
            this_line = re.split('\s{2,}', this_line[0])
        if is_heading(this_line):
            cattle = this_line[0]
        elif 'horse' in this_line[0].lower():
            break
        elif is_sale(this_line) and cattle:
            sale = default_sale.copy()
            sale.update(get_sale(this_line, cattle))
            writer.writerow(sale)


def write_sale_from_img(line, default_sale, writer):
    pattern = {} ## FIXEM
    for this_line in line:
        for this_pattern in pattern:
            match = this_pattern.search(line)
            if match:
                break
        if match:
            this_sale = match ## FIXME
            sale = default_sale.copy()
            sale.update(this_sale)
            writer.writerow(sale)


def main():

    # Locate existing CSV files
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # Use fancy webkit tools to execute javascript
    # phantom = webdriver.PhantomJS(desired_capabilities=DCAP)
    phantom = webdriver.PhantomJS()
    phantom.get(base_url + report_path)
    sleep(1)

    img = phantom.find_element_by_id('cjg9').find_element_by_tag_name('img')
    if img:
        from_img = True
        img_url = img.get_attribute('src')
        urlretrieve(img_url, str(temp_raw))
        temp_txt = temp_raw.with_suffix('.txt')
        tesseract = scrape_util.tesseract.format(
            str(temp_raw),
            str(temp_txt.with_suffix('')),
            prefix,
            )
        system(tesseract)
        with temp_txt.open('r') as io:
            line = list(this_line.strip() for this_line in io)
        temp_raw.clean()

        sys.exit() # FIXME
        # get to line, with a date line on top
    else:
        from_img = False
        div = phantom.find_elements_by_class_name('s4')

        # Tabulate text by pixel position
        # text = []
        # for this_div in div:
        #     top = float(this_div.value_of_css_property('top').strip('px'))
        #     left = float(this_div.value_of_css_property('left').strip('px'))
        #     value = this_div.text.strip()
        #     if value:
        #         text.append([top, left, this_div.text.strip()])
        text = [
            [element.location['y'], element.location['x'], element.text]
            for this_div in div for element in this_div.find_elements_by_xpath('*')
            ]
        text.sort(key = lambda x: x[:2])
        position_y = 0
        this_y = text[0][0]
        for this_text in text:
            last_y = this_y
            this_y = this_text[0]
            if (this_y - last_y) > PIXEL_GAP:
                position_y += 1
            this_text[0] = position_y
        line = [[k1 for k1, g1 in groupby(g0, key=lambda x: x[-1])] for k0, g0 in groupby(text, key=lambda x: x[0])]

        # position = 0
        # this_y = text[0][0]
        # for this_text in text:
        #     last_y = this_y
        #     this_y = this_text[0]
        #     if (this_y - last_y) > PIXEL_GAP:
        #         position += 1
        #     this_text[0] = position

        # report = []
        # for this_text in text:
        #     split = this_text[2].splitlines()
        #     n = len(split)
        #     for idx, this_split in enumerate(split):
        #         report.append([this_text[0] + idx / n, this_text[1], this_split])

        # report.sort(key = lambda x: (x[0], x[1]))
        # line = [[v[2] for v in g] for k, g in groupby(report, key = lambda x: x[0])]

    # Stop iteration if this report is already archived
    sale_date = get_sale_date(line)
    io_name = archive.new_csv(sale_date)
    if not io_name:
        return

    # Initialize the default sale dictionary
    this_default_sale = default_sale.copy()
    this_default_sale.update({
        'sale_year': sale_date.year,
        'sale_month': sale_date.month,
        'sale_day': sale_date.day,
        })

    # Open a new CSV file and write each sale
    with io_name.open('w', encoding='utf-8') as io:
        writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
        writer.writeheader()
        if from_img:
            write_sale_from_img(line, this_default_sale, writer)
        else:
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
