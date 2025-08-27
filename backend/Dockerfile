FROM python:3.10-slim

# Install dependencies for Chrome + Xvfb
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl xvfb \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Default command: run Flask with Gunicorn
# Wrap with xvfb-run so Chrome thinks there’s a monitor
CMD ["xvfb-run", "-a", "gunicorn", "-b", "0.0.0.0:5000", "app:app"]
