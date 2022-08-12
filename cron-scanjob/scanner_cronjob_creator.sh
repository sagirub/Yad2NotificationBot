#!bin/sh

# assume item_sconner_job.py located in /usr/local/bin
sudo crontab -l > mycron
sudo echo "*/30 9-21 * * 0-5 cd /usr/local/bin && sudo /usr/bin/python3 /user/local/bin/item_scanner_job.py" >> mycron
sudo crontab mycron
sudo rm mycron