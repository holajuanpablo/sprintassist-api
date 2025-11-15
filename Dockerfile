FROM python:3.11-slim

# Make sure logs are not buffered
ENV PYTHONUNBUFFERED=True

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --- Optional: Build-time checks ---
RUN echo "--- Listing /app contents after COPY ---"
RUN ls -lR /app
# --- End Optional: Build-time checks ---

# --- Run the application using Python and Waitress ---
CMD ["python", "app.py"]
