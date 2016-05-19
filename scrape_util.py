import re
import hashlib
from pathlib import Path
from sys import platform
from os.path import expanduser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_market(argv):

    roundup_website_id = Path(argv[0]).stem.split('_')[0]
    connect_args = {
        'option_files': expanduser('~') + '/.my.cnf',
        'option_groups': ['client', 'roundup-db'],
        }
    engine = create_engine(
        'mysql+mysqlconnector:///',
        connect_args=connect_args,
        echo=False,
        )
    Session = sessionmaker(bind=engine)
    session = Session()
    result = session.execute(
        "SELECT address.* "
        "FROM roundup_market "
        "JOIN address using(address_id) "
        "WHERE roundup_website_id = {} "
        "ORDER BY address.city".format(roundup_website_id)
        ).fetchall()
    if len(result) == 1:
        market = {'sale_' + k: v for k, v in result[0].items() if v}
        market = {k: v for k, v in market.items() if k in header}
    elif len(result) > 1:
        market = []
        for this_result in result:
            this_result = {'sale_' + k: v for k, v in this_result.items() if v}
            market.append({k: v for k, v in this_result.items() if k in header})
    else:
        market = {}
    website = session.execute(
        "SELECT website, script "
        "FROM roundup_website "
        "WHERE roundup_website_id = {}".format(roundup_website_id)
        ).first()
    url = 'http://' + website['website'] + '/'
    prefix = website['script']
    session.close()

    return market, url, prefix


def phantom():
    from selenium import webdriver
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

    dcap = dict(DesiredCapabilities.PHANTOMJS)
    dcap["phantomjs.page.settings.userAgent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 "
        "(KHTML, like Gecko) Chrome/15.0.87 "
        "livestock-market-research-bot/1.0 (itc2@georgetown.edu)"
    )
    return webdriver.PhantomJS(desired_capabilities=dcap)

url_header = {'user-agent': 'livestock-market-research-bot/1.0 (itc2@georgetown.edu)'}

coding = 'utf-8'

header = [
    'sale_year',          # Market report date
    'sale_month',
    'sale_day',
    'sale_title',         # Market report title
    'sale_head',          # Total number of cattle sold
    'sale_name',          # Livestock Market name, address
    'sale_address',
    'sale_po',
    'sale_city',
    'sale_state',
    'sale_zip',
    'consignor_name',     # Seller/Consignor name, address
    'consignor_address',
    'consignor_city',
    'consignor_state',
    'consignor_zip',
    'buyer_name',         # Buyer name, address (usually not available)
    'buyer_address',
    'buyer_city',
    'buyer_state',
    'buyer_zip',
    'cattle_cattle',      # Type of cattle, e.g. "blk heiffer"
    'cattle_head',        # Number of cattle
    'cattle_avg_weight',  # Average weight in pounds
    'cattle_price_cwt',   # Price per hundred weight in dollars
    'cattle_price',       # Price per head in dollars
    ]

default_cattle_clue = r'(bulls?|steers?|strs?|cows?|heifers?|hfrs?|calf|calves|pairs?)$'

state = '|'.join([
    r'\bAB\b', r'\bAlberta\b',
    r'\bAL\b', r'\bAlabama\b',
    r'\bAK\b', r'\bAlaska\b',
    r'\bAZ\b', r'\bArizona\b',
    r'\bAR\b', r'\bArkansas\b',
    r'\bCA\b', r'\bCalifornia\b',
    r'\bCO\b', r'\bColorado\b',
    r'\bCT\b', r'\bConnecticut\b',
    r'\bDE\b', r'\bDelaware\b',
    r'\bDC\b',
    r'\bFL\b', r'\bFlorida\b',
    r'\bGA\b', r'\bGeorgia\b',
    r'\bHI\b', r'\bHawaii\b',
    r'\bID\b', r'\bIdaho\b',
    r'\bIL\b', r'\bIllinois\b', r'\bIll\b',
    r'\bIN\b', r'\bIndiana\b',
    r'\bIA\b', r'\bIowa\b',
    r'\bKS\b', r'\bKansas\b',
    r'\bKY\b', r'\bKentucky\b',
    r'\bLA\b', r'\bLouisiana\b',
    r'\bME\b', r'\bMaine\b',
    r'\bMD\b', r'\bMaryland\b',
    r'\bMA\b', r'\bMassachusetts\b',
    r'\bMI\b', r'\bMichigan\b', r'\bMich\b',
    r'\bMN\b', r'\bMinnesota\b', r'\bMinn\b',
    r'\bMS\b', r'\bMississippi\b', r'\bMiss\b',
    r'\bMO\b', r'\bMissouri\b',
    r'\bMT\b', r'\bMontana\b', r'\bMont\b',
    r'\bNE\b', r'\bNebraska\b', r'\bNeb\b',
    r'\bNV\b', r'\bNevada\b',
    r'\bNH\b', r'\bNew Hampshire\b',
    r'\bNJ\b', r'\bNew Jersey\b',
    r'\bNM\b', r'\bNew Mexico\b',
    r'\bNY\b', r'\bNew York\b',
    r'\bNC\b', r'\bNorth Carolina\b',
    r'\bND\b', r'\bNorth Dakota\b', r'\bN.D\b',
    r'\bOH\b', r'\bOhio\b',
    r'\bOK\b', r'\bOklahoma\b', r'\bOkla\b',
    r'\bOR\b', r'\bOregon\b',
    r'\bPA\b', r'\bPennsylvania\b',
    r'\bRI\b', r'\bRhode Island\b',
    r'\bSC\b', r'\bSouth Carolina\b',
    r'\bSD\b', r'\bSouth Dakota\b', r'\bS.D\b',
    r'\bSK\b', r'\bSaskatchewan\b',
    r'\bTN\b', r'\bTennessee\b',
    r'\bTX\b', r'\bTexas\b',
    r'\bUT\b', r'\bUtah\b',
    r'\bVT\b', r'\bVermont\b',
    r'\bVA\b', r'\bVirginia\b',
    r'\bWA\b', r'\bWashington\b',
    r'\bWV\b', r'\bWest Virginia\b',
    r'\bWI\b', r'\bWisonsin\b',
    r'\bWY\b', r'\bWyoming\b', r'\bWyo\b',
    ])

if platform=='darwin':
    pdftotext = '/usr/local/bin/pdftotext -enc UTF-8 -q -table {}'
    gocr = '/usr/local/bin/gocr {} > {}'
    convert = '/usr/local/bin/convert {} {} {}'
    tesseract = '/usr/local/bin/tesseract -psm 6 {} {} {}'
elif platform=='linux':
    pdftotext = '/usr/local/bin/pdftotext -enc UTF-8 -q -table {}'
    gocr = '/usr/bin/gocr {} > {}'
    convert = '/usr/bin/convert {} {} {}'
    tesseract = '/usr/bin/tesseract -psm 6 {} {} {}'
elif platform=='win32':
    pdftotext = '"C:\Program Files\Xpdf\pdftotext.exe" -q -table {}'

def is_number(string):
    string = re.sub(r'[^\w\s]', '', string)
    try:
        float(string)
        return True
    except ValueError:
        return False

class ArchiveFolder(object):

    def __init__(self, argv, prefix):
        self.prefix = prefix
        self.archive = Path(argv[0]).parent / Path(self.prefix + '_scrape/dbased/')
        if not self.archive.exists():
            self.archive.mkdir(parents=True)
        
    def new_csv(self, sale_date, title=None):

        if not sale_date:
            return None

        io_name = self.prefix + '_' + sale_date.strftime('%y-%m-%d') 
        if title:
            title_hash = hashlib.md5(title.encode())
            io_name += '_' + title_hash.hexdigest()
        io_name = Path(io_name + '.csv')

        archive = self.archive / io_name
        if archive.exists():
            io_name = None
        else:
            io_name = self.archive.parent / io_name 

        return io_name

class ReportRaw(object):

    def __init__(self, argv, prefix, suffix='pdf'):
        path = Path(argv[0])
        self.prefix = prefix
        self.suffix = '.' + suffix
        self.folder = path.parents[0] / Path(self.prefix + '_scrape/' + suffix)
        self.raw = path.parents[0] / Path(self.prefix + '_scrape/') / Path('temp.' + suffix)
        self.dirty = []
        if not self.folder.exists():
            self.folder.mkdir(parents=True)

    def __str__(self):
        return str(self.raw)

    def clean(self, dirty=False):
        # Move downloaded temp file into the folder for archives
        with self.raw.open('rb') as io:
            hash = hashlib.md5(io.read())
        digest = hash.hexdigest()
        archive_name = self.prefix + '_' + digest + self.suffix
        archive = self.folder / Path(archive_name)
        try:
            self.raw.rename(archive)
        except FileExistsError:
            self.raw.unlink()

        # Remove temp files
        if not dirty:
            for item in list(self.dirty):
                item.unlink()
                self.dirty.remove(item)

    def with_suffix(self, *args, **kwargs):
        new = self.raw.with_suffix(*args, **kwargs)
        self.dirty.append(new)
        return new

    def open(self, *args, **kwargs):
        return self.raw.open(*args, **kwargs)
