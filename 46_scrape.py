import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
from datetime import datetime
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'Market_Reports.html'
strip_char = ';,. \n\t'
temp_raw = scrape_util.ReportRaw(argv, prefix)
sale_pattern = [
    re.compile(
        r'(?P<name>\S.*?)(?:\s{2,}|\s,\s+)'
        r'(?P<city>\S.*?)\s{2,}'
        r'(?P<head>\d+)\s+'
        r'(?P<cattle>\S.*?)\s{2,}'
        r'(?P<weight>[\d,]+)'
        r'(?P<price>[\s\.\d\$]+)'
        ),
    re.compile(
        r'(?P<name>\S.*?)(?:\s{2,}|,\s+)'
        r'(?P<city>\S.*?)\s{2,}'
        r'(?P<head>\d+)\s+'
        r'(?P<cattle>\S.*?)\s{2,}'
        r'(?P<weight>[\d,]+)'
        r'(?P<price>[\s\.\d\$]+)'
        ),
    ]


def get_sale_date(this_report):
    text = this_report.get_text()
    pattern = [
        r'(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<year>[0-9]+)',
        r'(?P<month>[0-9]+)/(?P<day>[0-9]+)-[0-9]+/(?P<year>[0-9]+)',
        r'(?P<month>[0-9]+)-(?P<day>[0-9]+)-(?P<year>[0-9]+)',
        ]
    for this_pattern in pattern:
        match = re.search(this_pattern, text)
        if match:
            sale_date = datetime(*map(int, [
                match.group('year'),
                match.group('month'),
                match.group('day')
                ]))
            break
    if not match:
        sale_date = None
    
    return sale_date


def get_sale_head(line):
    for this_line in line:
        if re.search(r'hd|head', this_line, re.IGNORECASE):
            match = re.search(r'([0-9]+)',this_line)
            if match:
                return match.group(1)
            

def is_sale(this_line):
    # cattle_clue = '(bulls?|steers?|strs?|stcf|cows?|heifers?|hfrs?|hf2|hfrcf|hfrtt|calf|calves|pairs?|pr)'
    # has_cattle = re.search(cattle_clue, this_line, re.IGNORECASE)
    has_price = re.search(r'\$\s*\d+\.\d{2}', this_line)
   
    # return all([has_cattle, has_price])
    return has_price


def is_head(this_line):
    has_head = re.search(r'head|hd', this_line, re.IGNORECASE)
    has_number = re.search(r'([0-9]+)', this_line)
   
    return all([has_head, has_number])


def get_sale_location(word):
    sale_location = ' '.join(word)
    if ',' in sale_location:
        sale_location = sale_location.split(',')
    else:
        match = re.search(r'(.*?)(' + scrape_util.state + ')', sale_location)
        if match:
            sale_location = [match.group(1), match.group(2)]
        else:
            sale_location = [sale_location]

    return sale_location


def is_number(string):
    string = re.sub(r'\$|[,-/]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False
        

def get_sale(line):

    for pattern in sale_pattern:
        match = pattern.search(line)
        if match:
            break

    sale = {
        'consignor_name': match.group('name').strip(strip_char).title(),
        'consignor_city': match.group('city').strip(strip_char).title(),
        'cattle_head': match.group('head'),
        'cattle_cattle': match.group('cattle').strip(strip_char).title(),
        }

    # number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))
    # comma_word = list(idx + 1 for idx in range(len(word)) if re.search(r',$', word[idx]))

    # if len(comma_word) == 0:
    #     comma_idx = number_word[0]
    # elif len(comma_word) == 1:
    #     comma_idx = comma_word[0]
    # elif re.search(scrape_util.state, ' '.join(word[comma_word[0]: comma_word[-1] + 1])):
    #     comma_idx = comma_word[-2]
    # else:
    #     comma_idx = comma_word[-1]

    # number_word = list(idx for idx in number_word if idx >= comma_idx)
    # sale_location = get_sale_location(word[comma_idx: number_word[0]])    
    
    # sale = {
    #     'consignor_name': ' '.join(word[0: comma_idx]).strip(strip_char).title(),
    #     'consignor_city': sale_location.pop(0).strip(strip_char).title(),
    #     'cattle_head': word[number_word[0]].strip(strip_char),
    #     'cattle_cattle': ' '.join(word[number_word[0] + 1:number_word[1]]).strip(strip_char),
    #     }
                
    # if sale_location:
    #     sale['consignor_state'] = sale_location.pop().strip(strip_char)

    weight_string = match.group('weight').strip(strip_char).replace(',', '')
    try:
        float(weight_string)
        sale.update({'cattle_avg_weight': weight_string})
    except ValueError:
        pass
        
    price_string = match.group('price')
    match = False
    if not match:
        match = re.search(r'\$([0-9,.]+)/?he?a?d?', price_string, re.IGNORECASE)
        target = 'cattle_price'
    if not match:
        match = re.search(r'\$([0-9,.]+)/?cw?t?', price_string, re.IGNORECASE)
        target = 'cattle_price_cwt'
    if not match:
        match = re.search(r'([0-9,.]+)', price_string, re.IGNORECASE)
        target = 'cattle_price_cwt'
    if match:
        sale[target] = match.group(1).replace(',','').strip(strip_char)
        
    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def main():
    
    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read())
    content = soup.find('div', id = 'content1')
    report = content.find_all('a')
    report.pop(0)

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        if not this_report.get_text():
            continue

        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)
        if not io_name:
            break

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # create temporary text file from downloaded pdf
        request = Request(
            base_url + this_report['href'],
            headers = scrape_util.url_header,
            )
        with urlopen(request) as io:
            response = io.read()
        with temp_raw.open('wb') as io:
            io.write(response)
        system(scrape_util.pdftotext.format(str(temp_raw)))

        # read sale text into line list
        temp_txt = temp_raw.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = list(this_line.strip() for this_line in io if is_sale(this_line))

        with temp_txt.open('r') as io:
            head_line = list(this_line.strip() for this_line in io if is_head(this_line))
        temp_raw.clean()

        sale_head = get_sale_head(head_line)
        
        this_default_sale.update({
            'sale_head': sale_head,
            })
        
        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()

            # extract & write sale dictionary
            for this_line in line:
                sale = this_default_sale.copy()
                sale.update(get_sale(this_line))
                if sale != this_default_sale:
                    writer.writerow(sale)

if __name__ == '__main__':
    main()
