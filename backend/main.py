import os, hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import jwt
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import (create_engine, Column, Integer, String, Boolean,
                        DateTime, ForeignKey)
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ---------- Config ----------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_HOURS = 24

# ---------- Database ----------
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), default="")
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)


Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Schemas ----------
class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    completed: Optional[bool] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    completed: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ---------- Auth helpers ----------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, h = stored.split("$")
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(check.hex(), h)


def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id),
               "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


bearer = HTTPBearer(auto_error=False)


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        data = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        user = db.get(User, int(data["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


# ---------- App ----------
app = FastAPI(title="Task Manager API")


@app.exception_handler(Exception)
async def unhandled(_, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------- Auth routes ----------
@app.post("/api/auth/register", status_code=201)
def register(data: Credentials, db: Session = Depends(get_db)):
    username = data.username.strip().lower()
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    user = User(username=username, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return {"token": create_token(user.id), "username": user.username}


@app.post("/api/auth/login")
def login(data: Credentials, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=data.username.strip().lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    return {"token": create_token(user.id), "username": user.username}


# ---------- Task routes ----------
def get_task_or_404(task_id: int, user: User, db: Session) -> Task:
    task = db.query(Task).filter_by(id=task_id, owner_id=user.id).first()
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@app.get("/api/tasks", response_model=List[TaskOut])
def list_tasks(filter: str = Query("all", pattern="^(all|completed|pending)$"),
               user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Task).filter_by(owner_id=user.id)
    if filter == "completed":
        q = q.filter(Task.completed.is_(True))
    elif filter == "pending":
        q = q.filter(Task.completed.is_(False))
    return q.order_by(Task.created_at.desc()).all()


@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    task = Task(title=data.title.strip(), description=data.description.strip(),
                owner_id=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def read_task(task_id: int, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    return get_task_or_404(task_id, user, db)


@app.put("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    task = get_task_or_404(task_id, user, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    db.delete(get_task_or_404(task_id, user, db))
    db.commit()


# ---------- Serve frontend (must be last) ----------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
