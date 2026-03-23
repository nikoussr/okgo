sudo -u postgres psql
cat /var/log/alltransfer/error.log
sudo journalctl -u alltransfer -f
sudo journalctl -u alltransfer | grep ТОКЕН
