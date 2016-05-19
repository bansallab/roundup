## Introduction
Project `roundup` is a collection of Python scripts that mine the web for data on cattle sales at US livestock markets (where animals are sold through live auctions).
Data are pulled from livestock markets with websites that post data in the form of "market reports" or "sale reports".
In particular, a website is a valid data source if the reports provide information on the location of a consignor (who brings cattle to market) or a buyer (who takes delivery from the market).
Different livestock market websites provide remarkably consistent types of information, but in drastically varying formats.
To systematically record cattle sales, a script is customized to "round up" data from each livestock market's website and write a commonly formatted CSV version to a locally stored archive.

### Collaboration
Contribution to and use of this repository is de facto restricted to collaborators with access to the associated database, which includes the website URLs among other private information. For collaborators contributing to the project, the following instructions will help you get started at writing a script to scrape a new website. The function `scrape_util.get_market` expects to find a working mysql client program and a configuration file for connecting to the database under group heading [roundup] at ~/.my.cnf. See the [MySQL reference manual](http://dev.mysql.com/doc/refman/5.7/en/option-files.html) for details.

### Getting Started

Python and git are the two basic tools you need to contribute. If you do not use a package manager (e.g. APT or Homebrew), you can download binaries from [git-scm.com](http://git-scm.com/downloads) and [python.org](http://python.org). Install the latest versions (Python 3.x). (Note for Windows users: the default install options for git are acceptable, but feel free to uncheck integration with Windows Explorer. If you opt not to modify your PATH variables, use the installed "git bash" shell to execute the git commands below.)

At minimum, two Python packages are required: `sqlalchemy`, `py-dateutil` and `BeautifulSoup4`. Experienced Python programmers excepted (who should install the packages however they want), install the packages from within Python (indicated by the the Python prompt `>>>`): 
```
>>> import pip
>>> pip.main(['install', 'sqlalchemy', 'py-dateutil', 'BeautifulSoup4'])
```

### Clone this Repository onto your Local Machine

Every file in this repository with a name like `*_scrape.py` is a script that converts the market reports found at a particular website to a CSV file. "Cloning" this repository copies all the files to your machine, giving you many examples to learn from and copy. From the command line of your shell (incl. git-bash on Windows), execute:
```
> cd /path/to/your/projects/
> git clone https://github.com/itcarroll/roundup.git
> cd roundup
```

The first step for adding a new `*_scrape.py` script is to obtain the unique identifier, `<id>`, associated with each market website in our private database.
You will create a "branch" of the repository for your work, which will be merged into the `master` branch when the script is complete.
Because every new branch should stem from the most up-to-date `master`, create your branch with the following:
```
> git checkout master
> git pull
> git checkout -b <branch_name>
> cp 214_scrape.py <id>_scrape.py
```
Use any branch name you want, it's not persistent. The `pull` command told git to update your local repository from GitHub.
The copied script is a template: open it up and start looking around.

When you successfully connect to the database and run your script, it will create folders `<prefix>_scrape` and `<prefix>_scrape/dbased`, where prefix is a friendlier string associated with the <id> previously obtained.
The first holds newly written CSV files, with names patterned after `<prefix>_YY-MM-DD.csv`.
The subfolder `dbased` will hold CSV files copied from `<prefix>_scrape` after being imported into the database by a cron job.
The importance of the subfolder here is that it holds market reports that have already been imported and should not be changed.
The script should and will overwrite CSV files in `<prefix>_scrape`, which will take many iterations to perfect.

So that Ian know's you've gotten started, commit your new file to the git repository and push the branch upstream to GitHub.
```
> git add <id>_scrape.py
> git commit -m 'initial commit'
> git push -u origin <branch_name>
```
For all subsequent versions of your script, make a commit and push your work to git hub like so
```
> git commit -am 'some message about the changes to <id>_scrape.py'
> git push
```

### Study the Details

Take a look at some online market reports, including the source (i.e. the raw HTML).
+ http://www.wisheklivestock.com/market.html
+ http://www.billingslivestock.com/Cow_Sales/Links/CS_Market.html
+ http://www.sterlinglivestock.com/Markets/index.php

Study the `214_scrape.py` Python script until you understand how it works.
+ Each function's docstring (the triple quoted text) describes its purpose.
+ Commented lines (preceded with `#`) describe the script's sections and/or logic.
+ The module `scrape_util.py` contains definitions used by all the `*_scrape.py` scripts, including the CSV headers for the data your script will collect.
+ The `main()` function exucutes the following sequence:
      1. Load the current collection of reports available online.
      1. Locate the collection of archived CSV files.
      1. Iterate through each report to:
         1. Read the sale date (see `5_scrape.py` for an example with multiple reports for a given day).
         1. Check the archive for an existing CSV file.
         1. Read the rows of the report into a list.
         1. Open a new CSV file and write a line for each row that represents a sale.

Use the Python debugger (pdb) to execute specific segments. Here is an example debugger session:
```
>>> import pdb
>>> from 214_scrape import *
>>> pdb.runcall(main)
> /path/to/your/projects/roundup/wishek_scrape.py(131)main()
-> url = base_url + report_path
(Pdb) l
126  	            writer.writerow(sale)
127  	
128  	def main():
129  	
130  	    # Get URLs for all reports
131  ->	    url = base_url + report_path
132  	    soup = BeautifulSoup(urllib.request.urlopen(url).read())
133  	    report = [soup]
134  	
135  	    # Locate existing CSV files
136  	    archive = scrape_util.ArchiveFolder(argv)
(Pdb) n
> /Users/icarroll/projects/cownet/roundup/wishek_scrape.py(132)main()
-> soup = BeautifulSoup(urllib.request.urlopen(url).read())
(Pdb) url
'http://www.wisheklivestock.com/market.htm'
(Pdb)
```

### Study these tools!

1. Navigate to a website's HTML to grab the list of market report URL's. The [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/bs4/doc/) package is instrumental, or you may require Selenium with the PhantomJS webdriver for pages heavy on javascript.
1. Sometimes the data are in a table, making the job easy. Sometimes each sale record is one string, which Python's [regular expressions module](https://docs.python.org/3/library/re.html?highlight=re#module-re) will help you parse.

### Note on Contributing

1. If you are new to Git, you might need these [tutorials](https://www.atlassian.com/git/tutorials). You may want to set up a [SSH key pair](https://github.com/settings/ssh).
1. Commit frequently with short, descriptive messages: `> git commit -am 'what I just did'`
1. Test your script by carefully inspecting the generated CSV files for errors.
1. Issue a pull request (from [here](https://github.com/itcarroll/roundup/branches)) to notify Ian when you need suggestions or the script is working!
1. To update your local copy with commits Ian pushes to the repo, run `git checkout <branch_name>` followed by `git pull`.
