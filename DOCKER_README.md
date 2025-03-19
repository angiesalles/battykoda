# Docker Setup for BattyCoda Django

This document explains how to use Docker with the BattyCoda Django application.

## Prerequisites

- Docker and Docker Compose installed on your system
- Basic knowledge of Docker and Django

## Setup

1. **Environment Variables**: 
   - Copy `.env.example` to `.env.local`
   - Update the values in `.env.local` as needed

2. **Build and Start Containers**:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

3. **Apply Migrations**:
   ```bash
   docker-compose exec web python manage.py migrate
   ```

4. **Create a Superuser** (first time only):
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

## Container Services

- **web**: Django application with Gunicorn
- **celery**: Celery worker for async tasks
- **flower**: Celery monitoring tool
- **redis**: Message broker for Celery
- **r-server-direct**: R script server for direct processing
- **r-server-original**: R script server for predictions

## Access Points

- Django web application: http://localhost:8060
- Flower dashboard: http://localhost:5555
- Admin interface: http://localhost:8060/admin

## Common Commands

- View logs:
  ```bash
  docker-compose logs -f web
  docker-compose logs -f celery
  ```

- Run Django management commands:
  ```bash
  docker-compose exec web python manage.py [command]
  ```

- Restart services:
  ```bash
  docker-compose restart web
  docker-compose restart celery
  ```

- Stop all services:
  ```bash
  docker-compose down
  ```

## Data Persistence

Data is persisted in Docker volumes:
- `data-volume`: For media files
- `redis-data`: For Redis data
- `r-libs`: For R packages

## Development Mode

For development, you can modify the Docker Compose file to mount your code directory and enable Django's development server instead of Gunicorn.