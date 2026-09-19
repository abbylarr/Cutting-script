"""
Project management endpoints for film projects.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.auth import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.processing_task import ProcessingTask
from app.models.film_project import FilmProject
from app.schemas.film_project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, 
    ProjectListResponse, SaveProjectRequest
)
from app.schemas.common import SuccessResponse, PaginatedResponse
from app.services.docx_generator import docx_generator
import os
import shutil

router = APIRouter()


@router.post("/save/{task_id}", response_model=SuccessResponse)
async def save_project_changes(
    task_id: UUID,
    save_request: SaveProjectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save project changes and optionally regenerate DOCX file.
    
    - **task_id**: ID of the processing task
    - **montage_rows**: Updated montage rows to save
    - **regenerate_docx**: Whether to regenerate the DOCX file
    - Returns success confirmation
    """
    # Get processing task and verify ownership
    task = db.query(ProcessingTask).filter(
        ProcessingTask.id == task_id,
        ProcessingTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing task not found"
        )
    
    # Get or create film project
    film_project = db.query(FilmProject).filter(
        FilmProject.task_id == task_id
    ).first()
    
    if not film_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Film project not found for this task"
        )
    
    try:
        # Convert Pydantic models to dict for storage
        rows = save_request.resolved_rows()
        rows_data = [row.dict() if hasattr(row, "dict") else row.model_dump() for row in rows]
        
        # Update both task result and project montage rows
        task.result = rows_data
        task.updated_at = func.now()
        
        film_project.montage_rows = rows_data
        film_project.updated_at = func.now()
        
        db.commit()
        
        # Regenerate DOCX if requested
        if save_request.regenerate_docx:
            try:
                await docx_generator.generate_docx_for_task(
                    task_id, 
                    rows_data, 
                    film_project.film_metadata
                )
            except Exception as e:
                # Log error but don't fail the save operation
                print(f"Warning: Failed to regenerate DOCX for task {task_id}: {e}")
        
        return SuccessResponse(
            message=f"Successfully saved project with {len(rows_data)} montage rows",
            data={
                "rows_saved": len(rows_data),
                "docx_regenerated": save_request.regenerate_docx
            }
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save project changes: {str(e)}"
        )


@router.get("/", response_model=PaginatedResponse)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in project titles"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all projects for the current user with pagination and search.
    
    - **page**: Page number (1-based)
    - **size**: Number of items per page
    - **search**: Optional search term for project titles
    - Returns paginated list of projects
    """
    # Build query
    query = db.query(FilmProject).filter(FilmProject.user_id == current_user.id)
    
    # Add search filter if provided
    if search:
        query = query.filter(FilmProject.title.ilike(f"%{search}%"))
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    projects = query.order_by(desc(FilmProject.updated_at)).offset((page - 1) * size).limit(size).all()
    
    # Convert to response format with task status
    items = []
    for project in projects:
        task = db.query(ProcessingTask).filter(ProcessingTask.id == project.task_id).first()
        task_status = task.status if task else "unknown"
        
        items.append(ProjectListResponse(
            id=project.id,
            title=project.title,
            created_at=project.created_at,
            updated_at=project.updated_at,
            status=task_status
        ))
    
    # Calculate total pages
    pages = (total + size - 1) // size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific project.
    
    - **project_id**: ID of the project
    - Returns complete project information including metadata and montage rows
    """
    project = db.query(FilmProject).filter(
        FilmProject.id == project_id,
        FilmProject.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        task_id=project.task_id,
        title=project.title,
        film_metadata=project.film_metadata,
        project_settings=project.project_settings,
        montage_rows=project.montage_rows,
        created_at=project.created_at,
        updated_at=project.updated_at
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    update_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update project metadata and settings.
    
    - **project_id**: ID of the project
    - **update_data**: Updated project information
    - Returns updated project information
    """
    project = db.query(FilmProject).filter(
        FilmProject.id == project_id,
        FilmProject.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    try:
        # Update fields if provided
        if update_data.title is not None:
            project.title = update_data.title
        
        if update_data.film_metadata is not None:
            project.film_metadata = update_data.film_metadata.dict()
        
        if update_data.project_settings is not None:
            project.project_settings = update_data.project_settings.dict()
        
        if update_data.montage_rows is not None:
            rows_data = [row.dict() for row in update_data.montage_rows]
            project.montage_rows = rows_data
            
            # Also update the associated task result
            task = db.query(ProcessingTask).filter(ProcessingTask.id == project.task_id).first()
            if task:
                task.result = rows_data
                task.updated_at = func.now()
        
        project.updated_at = func.now()
        db.commit()
        
        return ProjectResponse(
            id=project.id,
            user_id=project.user_id,
            task_id=project.task_id,
            title=project.title,
            film_metadata=project.film_metadata,
            project_settings=project.project_settings,
            montage_rows=project.montage_rows,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )


@router.delete("/{project_id}", response_model=SuccessResponse)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a project and clean up associated files.
    
    - **project_id**: ID of the project to delete
    - Returns success confirmation
    """
    project = db.query(FilmProject).filter(
        FilmProject.id == project_id,
        FilmProject.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    try:
        # Get associated task for file cleanup
        task = db.query(ProcessingTask).filter(ProcessingTask.id == project.task_id).first()
        
        # Clean up files
        if task:
            # Remove video file
            if task.video_path and os.path.exists(task.video_path):
                try:
                    os.remove(task.video_path)
                except OSError:
                    pass  # File might already be deleted
            
            # Remove SRT file if exists
            if task.srt_path and os.path.exists(task.srt_path):
                try:
                    os.remove(task.srt_path)
                except OSError:
                    pass
            
            # Remove DOCX file
            docx_path = os.path.join("output", str(current_user.id), f"montage_list_{task.id}.docx")
            if os.path.exists(docx_path):
                try:
                    os.remove(docx_path)
                except OSError:
                    pass
            
            # Remove user upload directory if empty
            user_upload_dir = os.path.join("uploads", str(current_user.id))
            if os.path.exists(user_upload_dir) and not os.listdir(user_upload_dir):
                try:
                    os.rmdir(user_upload_dir)
                except OSError:
                    pass
            
            # Remove user output directory if empty
            user_output_dir = os.path.join("output", str(current_user.id))
            if os.path.exists(user_output_dir) and not os.listdir(user_output_dir):
                try:
                    os.rmdir(user_output_dir)
                except OSError:
                    pass
        
        # Delete database records (task will be deleted due to foreign key cascade)
        db.delete(project)
        if task:
            db.delete(task)
        
        db.commit()
        
        return SuccessResponse(
            message=f"Successfully deleted project '{project.title}'",
            data={"project_id": str(project_id)}
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )


@router.post("/{project_id}/duplicate", response_model=ProjectResponse)
async def duplicate_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a duplicate of an existing project.
    
    - **project_id**: ID of the project to duplicate
    - Returns the new duplicated project
    """
    original_project = db.query(FilmProject).filter(
        FilmProject.id == project_id,
        FilmProject.user_id == current_user.id
    ).first()
    
    if not original_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    try:
        # Get original task
        original_task = db.query(ProcessingTask).filter(
            ProcessingTask.id == original_project.task_id
        ).first()
        
        if not original_task:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot duplicate project: original task not found"
            )
        
        # Create new task (copy of original)
        new_task = ProcessingTask(
            user_id=current_user.id,
            status="completed",  # Duplicated projects start as completed
            video_filename=f"Copy of {original_task.video_filename}",
            video_path=original_task.video_path,  # Reference same video file
            srt_path=original_task.srt_path,
            file_hash=original_task.file_hash,
            estimated_cost=original_task.estimated_cost,
            use_srt=original_task.use_srt,
            progress=1.0,
            current_step="completed",
            result=original_task.result
        )
        
        db.add(new_task)
        db.flush()  # Get the new task ID
        
        # Create new project
        new_project = FilmProject(
            user_id=current_user.id,
            task_id=new_task.id,
            title=f"Copy of {original_project.title}",
            film_metadata=original_project.film_metadata,
            montage_rows=original_project.montage_rows,
            project_settings=original_project.project_settings
        )
        
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        
        return ProjectResponse(
            id=new_project.id,
            user_id=new_project.user_id,
            task_id=new_project.task_id,
            title=new_project.title,
            film_metadata=new_project.film_metadata,
            project_settings=new_project.project_settings,
            montage_rows=new_project.montage_rows,
            created_at=new_project.created_at,
            updated_at=new_project.updated_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to duplicate project: {str(e)}"
        )