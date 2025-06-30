# Use a lightweight Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
# Using --no-cache-dir to reduce image size
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code into the container
COPY verse_bank.py .

ENV PATH="/usr/local/bin:${PATH}"
EXPOSE 5001

# Command to run your application using Gunicorn
# "verse_bank:app" assumes your Flask/FastAPI app instance is named 'app'
# within the 'verse_bank.py' file.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "verse_bank:app"]

