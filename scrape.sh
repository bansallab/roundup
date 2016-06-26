#!/bin/bash

echo 'START'
export TESSDATA_PREFIX=`dirname $0`
cd `dirname $0`
arx=dbased.tar.gz

echo '  START SCRAPE'
py=$(ls *_scrape.py)
for this_py in $py; do
  env/bin/python $this_py
  if [[ $? != 0 ]]; then
    echo '    CLEANUP from $this_py'
    id=$(echo $this_py | cut -d '_' -f 2)
    prefix=$(mysql -N -D cownet -e "select script from roundup_website where roundup_website_id = $id")
    rm $prefix_scrape/*.csv
  fi
done
echo '  END SCRAPE'

echo '  START ARCHIVE'
tar -czf $arx *_scrape/
gpg2 --no-tty -e -r itc2@georgetown.edu $arx
rm $arx
mv $arx.gpg ~/"Dropbox (Bansal Lab)"/Ian_Bansal_Lab/cownet/data/
echo '  END ARCHIVE'

echo '  START DROPBOX SYNC'
dropbox start
while [[ "$(dropbox status)" != "Up to date" ]]; do
  sleep 10
done
dropbox stop
echo '  END DROPBOX SYNC'

echo 'END'
