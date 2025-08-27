# Base Python image
FROM python:3.10-slim

# Install system dependencies for Chrome + Xvfb
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl xvfb \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && sh -c 'echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port (local use; Render overrides with $PORT)
EXPOSE 5000

# Start app with xvfb-run so Chrome has a fake display
CMD ["sh", "-c", "xvfb-run -a gunicorn --bind 0.0.0.0:${PORT:-5000} app:app"]
