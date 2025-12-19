# asgi.py
from main import app  # ton app FastAPI existante

# On "branche" l'UI sans modifier main.py
from ui import register_ui
register_ui(app)
