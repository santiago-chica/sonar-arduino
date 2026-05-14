from pydantic import BaseModel
from datetime import datetime

class EntryResponse(BaseModel):
    id: int
    distance: float
    angle: int
    timestamp: datetime
    
    class Config:
        orm_mode = True

class EntryCreate(BaseModel):
    distance: float
    angle: int