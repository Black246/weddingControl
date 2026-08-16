# WeddingControl

Plataforma personal para administrar una boda, sus invitados y futuras invitaciones digitales. La primera entrega incluye inicio de sesión, tablero y gestión de invitados; el modelo de datos ya separa organización y boda para permitir una futura versión multiusuario.

## Inicio rápido

1. Cree y active un entorno virtual con Python 3.12.
2. Instale las dependencias: `pip install -r backend/requirements.txt`.
3. Copie `backend/.env.example` como `backend/.env` y ajuste las variables.
4. Desde `backend`, ejecute `.\.venv\Scripts\python.exe -m flask --app run.py seed` y después `.\.venv\Scripts\python.exe -m flask --app run.py run --debug`.

Para desarrollo local puede usar SQLite. En producción use PostgreSQL y cambie obligatoriamente todas las claves.
