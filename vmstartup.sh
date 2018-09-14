#!/usr/bin/env sh
chmod o+rw /dev/ttyS2
chmod o+rw /dev/ttyS3
su -c "mkdir -p /home/adam/.cryptowatcher/default/monitor/logs" adam
cd /home/adam/.cryptowatcher/default/monitor/logs
su -c "touch alerts.log" adam
tail -f alerts.log > /dev/ttyS2 2>&1 &
cd /home/adam/app
while true; do 
  su -c "python3 -OO cryptowatcher.py > /dev/ttyS3 2>&1" adam
  sleep 5
done
