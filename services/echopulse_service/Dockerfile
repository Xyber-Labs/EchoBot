FROM python:3.12-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only the pyproject.toml to leverage Docker layer caching
COPY services/news_service/pyproject.toml ./

# Install dependencies from pyproject.toml
RUN pip install --no-cache-dir .

# Copy the rest of the application code
COPY . .

# Set PYTHONPATH to make imports work correctly from the root
ENV PYTHONPATH=/app

# Create and set permissions for media directories in a single layer
RUN mkdir -p /app/media/{news,voice,music,state,memory,videos,config} && \
    chmod -R 755 /app/media/

CMD ["python", "services/news_service/src/main.py"]