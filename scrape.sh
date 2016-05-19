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
    rm ${this_py%.py}/*.csv
  fi
done
echo '  END SCRAPE'

echo '  START ARCHIVE'
tar -czf $arx *_scrape/
gpg2 --no-tty -e -r itc2@georgetown.edu $arx
rm $arx
mv $arx.gpg ~/"Dropbox (Bansal Lab)"/Ian_Bansal_Lab/cownet/data/
echo '  END ARCHIVE'

# echo '  START DROPBOX SYNC'
# dropbox start
# while [[ "$(dropbox status)" != "Up to date" ]]; do
#   sleep 1
# done
# dropbox stop
# echo '  END DROPBOX SYNC'

echo 'END'
