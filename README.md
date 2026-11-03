# Task Manager

Full stack task manager built with FastAPI, SQLite/PostgreSQL, and HTML/CSS/JS.

## Features
- Register / Login (JWT)
- Add, edit, delete, complete tasks
- Filters: All / Pending / Completed
- Responsive UI with dark mode

## Run locally
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd backend
uvicorn main:app --reload

Open http://127.0.0.1:8000
API docs: http://127.0.0.1:8000/docs

## Live demo
ADD_LIVE_LINK_HERE
