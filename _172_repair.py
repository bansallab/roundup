from _172_scrape import *
from pathlib import Path


date_pattern = re.compile(r'\d{,2}(/|-)\d{,2}(/|-)\d{2,4}')


def get_sale_date(line):

    for idx, this_line in enumerate(line):
        match = date_pattern.search(this_line)
        if match:
            line[:idx + 1] = []
            break
    sale_date = dateutil.parser.parse(match.group(0)).date()

    return sale_date


def main():
    
    # get raw
    report = Path(prefix + '_scrape/pdf').glob('*.pdf')

    # locate storage
    archive = scrape_util.ArchiveFolder(argv, prefix)
    
    # write csv file for each historical report
    for this_report in report:

        # read raw
        system(scrape_util.pdftotext.format(str(this_report)))
        temp_txt = this_report.with_suffix('.txt')
        with temp_txt.open('r') as io:
            line = [this_line.strip() for this_line in io.readlines()]
        temp_txt.unlink()

        sale_date = get_sale_date(line)
        io_name = Path(prefix + '_scrape/' + prefix + '_' + sale_date.strftime('%y-%m-%d') + '.csv')

        sale_head = get_sale_head(line)
        this_default_sale = default_sale.copy()
        this_default_sale.update({
            'sale_year': sale_date.year,
            'sale_month': sale_date.month,
            'sale_day': sale_date.day,
            'sale_head': sale_head,
            })

        with io_name.open('w') as io:
            writer = csv.DictWriter(io, scrape_util.header, lineterminator='\n')
            writer.writeheader()
            write_sale(line, this_default_sale, writer)


if __name__ == '__main__':
    main()
