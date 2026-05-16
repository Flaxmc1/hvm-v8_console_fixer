# HOW TO FIX CONSOLE

# CLONE REPO 
``` git clone https://github.com/Flaxmc1/hvm-v8_console_fixer ```


#  GO TO DIRECTLY 
``` cd hvm-v8_console_fixer ```


#  INSTALL IMPORTANT PAKAGE 
``` sudo apt update && sudo apt install python3-pip -y && pip install flask ```


# RUN THE COMMAND
``` python3 ssh_fix.py ```


# RUN AS SYSTEMD
``` [Unit]
Description=HVM CONSOLE FIXER MADE BY NISSALOP2
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
WorkingDirectory=/root/ssh
ExecStart=/usr/bin/python3 /root/ssh/ssh_fix.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target ```



# START SSH FIXER
``` chmod +x /root/ssh/ssh_fix.py ```


# RUN ALL IMPORTANT CMD
``` systemctl daemon-reload
    systemctl start ssh_fix 
    systemctl enable ssh_fix ```

# CHECK STATUS

``` systemctl status ssh_fix ```


# CHECK LOGS IF ERROR

``` journalctl -u ssh_fix -n 20 --no-pager ```




** DM @nissalop22 If problem  **


HVM Owner: **@hopingboyz**
    
