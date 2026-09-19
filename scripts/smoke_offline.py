#!/usr/bin/env python3
"""Offline smoke: full pipeline without OpenAI."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
from datetime import datetime
from uuid import UUID

from app.db.base import init_db, SessionLocal
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.models.user import User
from app.services.auth import auth_service
from app.schemas.user import UserCreate
from app.services.task_queue import TaskProgressTracker, TaskInfo, TaskPriority
from app.schemas.processing_task import TaskStatus
from app.services.processing_runner import run_processing_job


async def main():
    init_db()
    video = ROOT / "tests/fixtures/smoke_video.mp4"
    if not video.exists():
        raise SystemExit(
            "Missing tests/fixtures/smoke_video.mp4 — see AUTONOMOUS.md"
        )

    db = SessionLocal()
    email = "smoke@example.com"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = auth_service.create_user(
            db, UserCreate(email=email, password="smoke12345")
        )

    task = ProcessingTask(
        user_id=user.id,
        video_filename="smoke_video.mp4",
        video_path=str(video.resolve()),
        status="pending",
        use_srt=False,
        progress=0.0,
    )
    db.add(task)
    db.flush()
    meta = {
        "title": "Smoke Test",
        "production_company": "Test",
        "year": 2026,
        "country": "Россия",
        "screenwriters": ["Test"],
        "copyright_holders": ["Test"],
        "duration": "00:00:08",
        "episodes_count": 1,
        "format": "Digital",
        "color_type": "Цветной",
        "media_carrier": "Файл",
        "original_language": "Русский",
        "audio_language": "Русский",
    }
    db.add(
        FilmProject(
            user_id=user.id,
            task_id=task.id,
            title="Smoke Test",
            film_metadata=meta,
            project_settings={
                "timecode_start": "01:00:00:00",
                "standard": "ГФФ",
                "fps": 25,
            },
        )
    )
    db.commit()
    db.refresh(task)
    task_id, user_id = str(task.id), str(user.id)
    db.close()

    info = TaskInfo(
        task_id=task_id,
        user_id=user_id,
        priority=TaskPriority.HIGH,
        created_at=datetime.utcnow(),
        status=TaskStatus.PROCESSING,
        started_at=datetime.utcnow(),
    )
    result = await run_processing_job(
        TaskProgressTracker(task_id, info),
        task_id=task_id,
        user_id=user_id,
        video_path=str(video.resolve()),
        use_srt=False,
        film_metadata=meta,
        project_settings={
            "timecode_start": "01:00:00:00",
            "standard": "ГФФ",
            "fps": 25,
        },
    )
    print("OK", result)
    db2 = SessionLocal()
    t = db2.query(ProcessingTask).filter(ProcessingTask.id == UUID(task_id)).first()
    assert t.status == "completed", t.error_message
    assert t.result and len(t.result) >= 1
    assert Path(result["docx_path"]).exists()
    print("PASS", "rows=", len(t.result), "docx=", result["docx_path"])
    db2.close()


if __name__ == "__main__":
    asyncio.run(main())
