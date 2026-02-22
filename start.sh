#!/bin/bash

apt-get update
apt-get install -y chromium

python bot.py
