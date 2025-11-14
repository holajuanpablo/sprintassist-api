FROM python:3.11-slim

# Make sure logs are not buffered
ENV PYTHONUNBUFFERED=True

WORKDIR /app

# COPY requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# COPY the rest of the application
COPY . .

# --- Optional: Build-time checks (can be kept or removed) ---
RUN echo "--- Listing /app contents after COPY ---"
RUN ls -lR /app

RUN echo "--- Checking for templates directory ---"
RUN if [ -d "/app/templates" ]; then echo "Found /app/templates"; ls -l /app/templates; else echo "ERROR: /app/templates NOT FOUND"; fi

RUN echo "--- Checking for index.html ---"
RUN if [ -f "/app/templates/index.html" ]; then echo "Found /app/templates/index.html"; else echo "ERROR: /app/templates/index.html NOT FOUND"; fi
# --- End Optional: Build-time checks ---

# --- Run the application using Gunicorn ---
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--log-level", "debug", "app:app"]
