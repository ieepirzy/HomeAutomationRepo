# 1. Base image with Python
FROM python:3.11-slim

# 2. Set working directory inside container
WORKDIR /app

# 3. Copy requirements first (for caching)
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the app
COPY . .

# 6. Expose port Flask will run on
EXPOSE 5000

# 7. Define the default command
CMD ["python", "wizapp.py"]