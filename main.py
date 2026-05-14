from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dto.entry import EntryCreate, EntryResponse
from models.entry import SessionLocal, SonarEntry
import serial
import serial.tools.list_ports
from datetime import datetime
import dateparser 

SERIAL_PORT = 'COM5'
BAUD_RATE = 9600
RETRY_INTERVAL = 2.0


class BroadcastHub:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    async def publish(self, payload: dict) -> None:
        for q in self._queues:
            await q.put(payload)


hub = BroadcastHub()


async def wait_for_serial() -> serial.Serial:
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"[serial] Conectado a {SERIAL_PORT}")
            return ser
        except serial.SerialException:
            print(f"[serial] {SERIAL_PORT} no disponible reintentando en {RETRY_INTERVAL} segundos")
            await asyncio.sleep(RETRY_INTERVAL)


async def serial_reader(ser: serial.Serial) -> None:
    loop = asyncio.get_running_loop()

    while True:
        try:
            raw: bytes = await loop.run_in_executor(None, ser.readline)
        except serial.SerialException as exc:
            print(f"[serial] Error al leer: {exc}")
            break

        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        
        print("LINEA:", line)
        
        try:
            data = EntryCreate.model_validate_json(str(line))
        except Exception as exc:
            print(f"[serial] Error al parsear json: {exc}")
            continue

        db = SessionLocal()
        try:
            db_entry = SonarEntry(distance=data.distance, angle=data.angle)
            db.add(db_entry)
            db.commit()
            db.refresh(db_entry)
            response = map_entry_to_response(db_entry)
        except Exception as exc:
            print(f"[serial] error db: {exc}")
            db.rollback()
            continue
        finally:
            db.close()

        await hub.publish(response.model_dump(mode="json"))



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    ser = await wait_for_serial()
    task = asyncio.create_task(serial_reader(ser))
    try:
        yield
    finally:
        task.cancel()
        ser.close()


app = FastAPI(title="SONAR arduino", lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def map_entry_to_response(entry: SonarEntry) -> EntryResponse:
    return EntryResponse(
        id=entry.id,
        distance=entry.distance,
        angle=entry.angle,
        timestamp=entry.timestamp,
    )



@app.post("/sonar", response_model=EntryResponse)
def create_sonar_entry(entry: EntryCreate, db: Session = Depends(get_db)) -> EntryResponse:
    db_entry = SonarEntry(distance=entry.distance, angle=entry.angle)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return map_entry_to_response(db_entry)


@app.get("/sonar/{entry_id}", response_model=EntryResponse)
def read_sonar_entry(entry_id: int, db: Session = Depends(get_db)) -> EntryResponse:
    db_entry = db.query(SonarEntry).filter(SonarEntry.id == entry_id).first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return map_entry_to_response(db_entry)

@app.get("/sonar/timestamp/{timestamp_from}/{timestamp_to}", response_model=list[EntryResponse])
def read_sonar_entry_timestamp(timestamp_from: str, timestamp_to: str, db: Session = Depends(get_db)) -> list[EntryResponse]:
    try:
        from_time: datetime = dateparser.parse(timestamp_from)
        to_time: datetime = dateparser.parse(timestamp_to)
        
        assert from_time is not None
        assert to_time is not None
    except:
        raise HTTPException(status_code=400, detail="Formatos de tiempo inválidos")
    
    db_entry: list[SonarEntry] = db.query(SonarEntry).filter(
        SonarEntry.timestamp >= from_time,
        SonarEntry.timestamp <= to_time
    ).all()
    
    return [
        map_entry_to_response(entry)
        for entry in db_entry
    ]

@app.get("/sonar/id/{origin}/{to}", response_model=list[EntryResponse])
def read_sonar_range(origin: int, to: int, db: Session = Depends(get_db)) -> list[EntryResponse]:
    db_entry: list[SonarEntry] = db.query(SonarEntry).filter(
        SonarEntry.id >= origin,
        SonarEntry.id <= to
    ).all()
    
    return [
        map_entry_to_response(entry)
        for entry in db_entry
    ]
    
    
@app.websocket("/ws/sonar")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    q = hub.subscribe()
    try:
        while True:
            payload = await q.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        print("[ws] Client disconnected")
    finally:
        hub.unsubscribe(q)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)