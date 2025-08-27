# Base image
FROM python:3.10-slim

# Install dependencies for Chrome + Xvfb
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl xvfb \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port (Render will override with its own, but we declare it anyway)
EXPOSE 5000

# Run app with Xvfb + Gunicorn bound to Render's $PORT
CMD ["sh", "-c", "xvfb-run -a gunicorn -b 0.0.0.0:${PORT} app:app"]
