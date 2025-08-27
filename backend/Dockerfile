FROM python:3.10-slim

# Install dependencies for Chrome + Xvfb
RUN apt-get update && apt-get install -y \
    wget gnupg2 unzip curl xvfb \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Default command: run Flask with Gunicorn wrapped in xvfb-run
CMD ["xvfb-run", "-a", "gunicorn", "-b", "0.0.0.0:5000", "app:app"]
