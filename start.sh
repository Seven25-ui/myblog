#!/data/data/com.termux/files/usr/bin/bash

# 1️⃣ Start Flask app in background
echo "Starting Flask app..."
python app.py &

FLASK_PID=$!

# 2️⃣ Wait for Flask to start
sleep 3

# 3️⃣ Start ngrok tunnel
echo "Starting ngrok..."
./ngrok http 5000
