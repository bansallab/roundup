import csv
from urllib.request import Request, urlopen
import re
from sys import argv
from bs4 import BeautifulSoup
import dateutil.parser
from os import system
import scrape_util


default_sale, base_url, prefix = scrape_util.get_market(argv)
report_path = 'reports/archives.php'
strip_char = ';,. \n\t'
temp_raw = scrape_util.ReportRaw(argv, prefix)
    

def get_sale_date(this_report):
    date_string = this_report.string
    date_string = re.sub(r'&.*?[0-9]+', '', date_string)
    sale_date = dateutil.parser.parse(date_string, fuzzy = True)
    return sale_date


def is_sale(this_line):
    is_not_succinct = len(re.split(r'\s{2,}',this_line)) > 3
    has_price = re.search(r'[0-9,]+\.[0-9]{2}', this_line)
   
    return all([is_not_succinct, has_price])


def is_number(string):
    string = re.sub(r'\$|[,-/#]|cwt|he?a?d?', '', string, flags = re.IGNORECASE)
    try:
        float(string)
        return True
    except ValueError:
        return False
        

def get_sale(word):
    
    number_word = list(idx for idx in range(len(word)) if is_number(word[idx]))

    sale = {
        'consignor_name': ' '.join(word[0:number_word[0]-2]).strip(strip_char),
        'consignor_city': word[number_word[0]-2].strip(strip_char).title(),
        'consignor_state': word[number_word[0]-1].strip(strip_char).upper(),
        'cattle_cattle': ' '.join(word[number_word[0]+1:number_word[1]]).strip(strip_char),
        }

    head_string = word[number_word.pop(0)].strip(strip_char).replace(',','')
    try:
        int(head_string)
        sale.update({'cattle_head': head_string})
    except ValueError:
        pass
        
    price_string = word[number_word.pop()]
    match = False
    if not match:
        match = re.search(r'([0-9,.]+) ?/?he?a?d?', price_string, re.IGNORECASE)
        key = 'cattle_price'
    if not match:
        match = re.search(r'([0-9,.]+) ?/?c?w?t?', price_string, re.IGNORECASE)
        key = 'cattle_price_cwt'
    if match:
        sale[key] = match.group(1).replace(',','').strip(strip_char)

    if number_word:
        weight_string = word[number_word.pop()].strip(strip_char).replace(',', '').replace('#','')
        try:
            float(weight_string)
            sale.update({'cattle_avg_weight': weight_string})
        except ValueError:
            pass

    sale = {k:v for k,v in sale.items() if v}
    
    return sale


def main():
    
    # get URLs for all reports
    request = Request(
        base_url + report_path,
        headers = scrape_util.url_header,
        )
    with urlopen(request) as io:
        soup = BeautifulSoup(io.read(), 'lxml')
    content = soup.find('div', id = 'pageContent')
    past_report = content.find_all('a')
    past_report.pop()
    side_content = soup.find('div', attrs={'class': 'content'}).find_all('div')[1]
    recent_report = side_content.find_all('a')
    report = past_report + recent_report

    # Identify existing reports
    archive = scrape_util.ArchiveFolder(argv, prefix)

    # write csv file for each historical report
    for this_report in report:

        sale_date = get_sale_date(this_report)
        io_name = archive.new_csv(sale_date)
        if not io_name:
            continue

        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            })

        # create temporary text file from downloaded pdf
        pdf_url = base_url + this_report['href']
        pdf_url = pdf_url.replace('/..','')
        request = Request(
            pdf_url,
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
            line = list(this_line.replace('\xa0', ' ').strip() for this_line in io if is_sale(this_line))
        temp_raw.clean()

        # open csv file and write header
        with io_name.open('w', encoding='utf-8') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()

            # extract & write sale dictionary
            for this_line in line:
                word = re.split(r'\s{2,}',this_line)
                sale = this_default_sale.copy()
                sale.update(get_sale(word))
                if sale != this_default_sale:
                    writer.writerow(sale)


if __name__ == '__main__':
    main()
