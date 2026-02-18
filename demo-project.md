# Task Manager API

A collaborative REST API built and maintained by marksync agents.

## Dependencies

```text markpact:deps python
fastapi==0.115.0
uvicorn[standard]
pydantic>=2.0
```

## Data Models

```python markpact:file path=app/models.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Task(BaseModel):
    id: Optional[int] = None
    title: str
    description: str = ""
    status: str = "todo"
    created_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Implement auth",
                "description": "Add JWT authentication",
                "status": "todo",
            }
        }
```

## API Server

```python markpact:file path=app/main.py
from fastapi import FastAPI, HTTPException
from datetime import datetime
from app.models import Task

app = FastAPI(
    title="Task Manager",
    description="Collaborative task API managed by marksync agents",
    version="0.1.0",
)

tasks: dict[int, Task] = {}
next_id = 1


@app.get("/")
def root():
    return {
        "service": "Task Manager",
        "version": "0.1.0",
        "tasks_count": len(tasks),
    }


@app.get("/tasks")
def list_tasks(status: str | None = None):
    result = list(tasks.values())
    if status:
        result = [t for t in result if t.status == status]
    return result


@app.post("/tasks", status_code=201)
def create_task(task: Task):
    global next_id
    task.id = next_id
    task.created_at = datetime.now()
    tasks[next_id] = task
    next_id += 1
    return task


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, updates: dict):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = tasks[task_id]
    for key, value in updates.items():
        if hasattr(task, key):
            setattr(task, key, value)
    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    del tasks[task_id]
    return {"deleted": task_id}


@app.get("/health")
def health():
    return {"status": "healthy", "tasks": len(tasks)}
```

## Run Command

```bash markpact:run
uvicorn app.main:app --host 0.0.0.0 --port ${MARKPACT_PORT:-8088}
```
