#python 3.10 is what the webscraper uses 
#idk if python 3.11 or 3.12 works
FROM python:3.10-slim

RUN apt-get update && apt-get install -y wget gnupg2 curl unzip \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose Flask port
EXPOSE 5000

#Start Flask with Gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:${PORT}"]