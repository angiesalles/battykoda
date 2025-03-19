# BattyCoda Django Application

## About
BattyCoda is a tool for analyzing animal vocalizations, including but not limited to bat echolocation, bird songs, frog calls, and other animal sounds. This is the Django-based implementation of the web application.

## Setup

### Prerequisites
- Python 3.8+
- Django 5.0+
- Additional dependencies in requirements.txt

### Installation
1. Clone the repository
2. Create a virtual environment: `python -m venv .venv`
3. Activate the environment: 
   - Unix/Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Apply migrations: `python manage.py migrate`
6. Create a superuser: `python manage.py createsuperuser`
7. Run the development server: `python manage.py runserver`

## Project Structure
- `config/` - Django project settings
- `battycoda_app/` - Main application code
- `templates/` - HTML templates
- `static/` - Static files (CSS, JS, images)
- `media/` - User-uploaded files

## License
See the LICENSE file for details.