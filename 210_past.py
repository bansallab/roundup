import csv
import dateutil.parser
import re
from pathlib import Path
from sys import argv
from os import system
import scrape_util

 
default_sale, base_url, prefix = scrape_util.get_market(argv)
strip_char = ';,. \n\t'


def get_sale_date(report_name):
    """Return the date of the sale."""

    match = re.search(r'(-.+?-[0-9]+-[0-9]+)', report_name)
    if match:
        sale_date = dateutil.parser.parse(match.group(1), fuzzy = True)
        return sale_date


def get_sale_head(line):
    """Return the total number of head sold at the sale.
    If present, the number is usually at the top of the market report."""
    
    for this_line in line:
        match = re.search(r'([0-9,]+)\s*(head|cattle)?.*sold', this_line, re.IGNORECASE)
        if match:
            return match.group(1).replace(',', '')


def is_sale(this_line):
    """Determine whether a given line describes a sale of cattle."""

    is_not_succinct = len(re.split(r'\s{3,}', this_line)) > 3
    has_price = re.search(r'[0-9]+\.[0-9]{2}', this_line)

    return bool(has_price and is_not_succinct)


def get_sale_location(word):
    """Convert address strings into a list of address components."""

    sale_location = ' '.join(word)
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
        string = re.sub(r'\$|[,-/]|(cw?t?)|(he?a?d?)', '', string, flags = re.IGNORECASE)
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

    if not is_number(word[len(word)-1]):
        price_word = ' '.join(word[len(word)-2:])
        word.pop()
        word.pop()
        word.append(price_word)

    number_word = [idx for idx, val in enumerate(word) if is_number(val)]

    name_location = ' '.join(word[0:number_word[0]])
    location_match = re.search(r'\[(.*)\]', name_location,re.IGNORECASE)
    if location_match:
        sale_location = [location_match.group(1).strip()]
        consignor_name = name_location.replace(location_match.group(),'')
        sale_location = get_sale_location(sale_location)
    else:
        location_incomplete_match = re.search(r'\[(.*)', name_location,re.IGNORECASE)
        if location_incomplete_match:
            consignor_name = name_location.replace(location_incomplete_match.group(),'')
            sale_location = []
        else:
            if len(name_location) == 41:
                consignor_name = name_location
                sale_location = []
            else:
                second_location_match = re.search(r'([a-z]+ ?, ?)(' + scrape_util.state + r')$', name_location, re.IGNORECASE)
                if second_location_match:
                    sale_location = [second_location_match.group().strip()]
                    consignor_name = name_location.replace(second_location_match.group(),'')
                    sale_location = get_sale_location(sale_location)
                else:
                    consignor_name = name_location
                    sale_location = []

    sale = {
        'consignor_name': consignor_name.strip(strip_char).title(),
        'cattle_cattle': ' '.join(word[number_word[0]+1:number_word[1]])
        }

    if sale_location:
        sale['consignor_city'] = sale_location.pop(0).strip(strip_char).title()
    if sale_location:
        sale['consignor_state'] = sale_location.pop().strip(strip_char)

    head_string = word[number_word.pop(0)].strip(strip_char).replace(',', '')
    try:
        int(head_string)
        sale['cattle_head'] = head_string
    except ValueError:
        pass

    price_string = word[number_word.pop()]

    if number_word:
        weight_string = word[number_word.pop()].strip(strip_char).replace(',', '')
        try:
            float(weight_string)
            sale['cattle_avg_weight'] = weight_string
        except ValueError:
            pass
        orig_key = 'cattle_price_cwt'
    else:
        orig_key = 'cattle_price'

    match = False
    if not match:
        match = re.search(r'([0-9,.]+)\s*/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+)\s*/?cw?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if not match:
        match = re.search(r'([0-9,.]+)', price_string, re.IGNORECASE)
        key = orig_key
    if match:
        sale[key] = match.group(1).replace(',', '').strip(strip_char)

    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def write_sale(line, this_default_sale, writer):
    """Extract sales from a list of report lines and write them to a CSV file."""
    
    for this_line in line:
        if is_sale(this_line):
            sale = this_default_sale.copy()
            word = re.split(r'\s{2,}',this_line)
            sale.update(get_sale(word))
            writer.writerow(sale)


def main():

    report_path = Path(argv[0]).parent / Path(prefix + '_past')
    past_report = report_path.glob('*.pdf')
    archive = scrape_util.ArchiveFolder(argv, prefix)

    for this_report in past_report:

        sale_date = get_sale_date(this_report.name)
        io_name = archive.new_csv(sale_date)

        # Stop iteration if this report is already archived
        if not io_name:
            break

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        system(scrape_util.pdftotext.format(str(this_report)))
        this_report_txt = this_report.with_suffix('.txt')
        with this_report_txt.open('r') as io:
            line = list(this_line.strip() for this_line in io)

        sale_head = get_sale_head(line)
        this_default_sale['sale_head'] = sale_head

        # Open a new CSV file and write each sale
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
