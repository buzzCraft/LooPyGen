#!/bin/sh

cd /var/www/html
python3 minter/LooPyMinty.py --json minter/metadata-cids.json $@
