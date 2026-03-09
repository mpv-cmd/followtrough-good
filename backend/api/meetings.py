from fastapi import APIRouter, UploadFile, File
from backend.services.meeting_service import process_meeting

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.post("/upload")
async def upload_meeting(file: UploadFile = File(...)):
    result = await process_meeting(file)
    return result