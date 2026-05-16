# 🔧 HVM Console Fixer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.x](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)

A robust solution for fixing console connectivity issues in HVM environments. This tool provides an automated web-based interface to resolve common SSH console problems.

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Quick Installation](#-quick-installation)
- [Manual Setup](#-manual-setup)
- [Running as Systemd Service](#-running-as-systemd-service)
- [Management Commands](#-management-commands)
- [Troubleshooting](#-troubleshooting)
- [Support](#-support)
- [Credits](#-credits)

## ✨ Features

- 🔄 Automatic console connection recovery
- 🌐 Web-based management interface
- 🚀 Systemd integration for reliability
- 📊 Real-time logging and monitoring
- 🔒 Secure root-level operations
- ⚡ Zero-downtime operation with auto-restart

## 📦 Prerequisites

- Ubuntu/Debian-based system
- Root access or sudo privileges
- Internet connection
- Python 3.x installed

## 🚀 Quick Installation

 # bash
# Clone the repository
git clone https://github.com/Flaxmc1/hvm-v8_console_fixer.git

# Navigate to project directory
cd hvm-v8_console_fixer

# Run automated setup
chmod +x setup.sh && sudo ./setup.sh

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
` nano /etc/systemd/system/ssh_fix.service ` 


` [Unit]
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

WantedBy=multi-user.target `





# RUN ALL IMPORTANT CMD
` systemctl daemon-reload
    systemctl start ssh_fix 
    systemctl enable ssh_fix`

# CHECK STATUS

` systemctl status ssh_fix `


# CHECK LOGS IF ERROR

`journalctl -u ssh_fix -n 20 --no-pager`




** DM @nissalop22 If problem  **


HVM Owner: **@hopingboyz**
