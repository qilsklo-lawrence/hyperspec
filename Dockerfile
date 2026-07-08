# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
# Copy package files
COPY frontend/package*.json ./
RUN npm install
# Copy the rest of the frontend source
COPY frontend/ ./
# Build the frontend
RUN npm run build

# Stage 2: Build the backend and final image
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy backend source code
COPY . .

# Copy the built frontend static files from Stage 1
# Note: app.py is configured to serve static files from 'frontend/dist'
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure the uploads directory exists (Cloud Run provides an ephemeral filesystem)
RUN mkdir -p /app/uploads

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 8080

# Command to run the application using gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
