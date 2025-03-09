#!/bin/sh
cd /Users/ryandemboski/Desktop/Developer/TTPorkheffley  # Set this to your actual project root

export TTR_PLAYCOOKIE="Username2"
export TTR_GAMESERVER="127.0.0.1"

# Set PYTHONPATH to the root of your project
#export PYTHONPATH="/Users/ryandemboski/.pyenv/versions/3.9.14/bin/python"

# Run Toontown with debugging enabled
python3 -m toontown.toonbase.ToontownStart #--debug