# Ella Backend

## Prerequisites
- Python 3.9+
- pip
- virtualenv

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/ella-backend.git
cd ella-backend
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
1. Copy `.env.example` to `.env`
2. Fill in the required environment variables

### 5. Database Setup
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Run the Application
```bash
python manage.py runserver
```

## Environment Variables
- `DATABASE_URL`: PostgreSQL database connection string
- `SECRET_KEY`: Django secret key
- `MISTRAL_API_KEY`: Mistral AI API key
- `GROQ_API_KEY`: Groq API key
- `DJANGO_ENVIRONMENT`: `development` or `production`

## Deployment
Deployed on Heroku. For production deployment, ensure all environment variables are set.

## Contributing
1. Create a virtual environment
2. Install dependencies
3. Create a `.env` file
4. Submit a pull request
