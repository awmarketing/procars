from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Response, Header, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import sys
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Verificar variables de entorno críticas
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME')

if not mongo_url or not db_name:
    logging.error("❌ MONGO_URL o DB_NAME no configuradas")
    logging.error("Configura estas variables en Railway → Variables")
    sys.exit(1)

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI()
api_router = APIRouter(prefix="/api")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "car-inspection"
storage_key = None

def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    try:
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        return storage_key
    except Exception as e:
        logging.error(f"Storage init failed: {e}")
        raise

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str) -> tuple:
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

class MechanicalInspection(BaseModel):
    engine: str = ""
    transmission: str = ""
    brakes: str = ""
    suspension: str = ""
    notes: str = ""

class CosmeticInspection(BaseModel):
    paint: str = ""
    interior: str = ""
    exterior: str = ""
    notes: str = ""

class CarInspection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    brand: str
    model: str
    year: int
    mileage: int
    purchase_price: float
    estimated_sale_price: float = 0.0
    mechanical: MechanicalInspection = Field(default_factory=MechanicalInspection)
    cosmetic: CosmeticInspection = Field(default_factory=CosmeticInspection)
    photos: List[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CarInspectionCreate(BaseModel):
    brand: str
    model: str
    year: int
    mileage: int
    purchase_price: float
    estimated_sale_price: float = 0.0
    mechanical: Optional[MechanicalInspection] = None
    cosmetic: Optional[CosmeticInspection] = None
    notes: str = ""

class CarInspectionUpdate(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    mileage: Optional[int] = None
    purchase_price: Optional[float] = None
    estimated_sale_price: Optional[float] = None
    mechanical: Optional[MechanicalInspection] = None
    cosmetic: Optional[CosmeticInspection] = None
    notes: Optional[str] = None

class PhotoUploadResponse(BaseModel):
    photo_url: str
    path: str


# Health check endpoints
@app.get("/")
async def root():
    return {
        "service": "Car Inspection Pro API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    try:
        await db.command("ping")
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

@api_router.post("/inspections", response_model=CarInspection)
async def create_inspection(input: CarInspectionCreate):
    inspection_dict = input.model_dump()
    
    if inspection_dict.get('mechanical') is None:
        inspection_dict['mechanical'] = MechanicalInspection()
    if inspection_dict.get('cosmetic') is None:
        inspection_dict['cosmetic'] = CosmeticInspection()
    
    inspection_obj = CarInspection(**inspection_dict)
    
    doc = inspection_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    
    await db.inspections.insert_one(doc)
    return inspection_obj

@api_router.get("/inspections", response_model=List[CarInspection])
async def get_inspections():
    inspections = await db.inspections.find({}, {"_id": 0}).to_list(1000)
    
    for inspection in inspections:
        if isinstance(inspection['created_at'], str):
            inspection['created_at'] = datetime.fromisoformat(inspection['created_at'])
        if isinstance(inspection['updated_at'], str):
            inspection['updated_at'] = datetime.fromisoformat(inspection['updated_at'])
    
    return inspections

@api_router.get("/inspections/{inspection_id}", response_model=CarInspection)
async def get_inspection(inspection_id: str):
    inspection = await db.inspections.find_one({"id": inspection_id}, {"_id": 0})
    
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    if isinstance(inspection['created_at'], str):
        inspection['created_at'] = datetime.fromisoformat(inspection['created_at'])
    if isinstance(inspection['updated_at'], str):
        inspection['updated_at'] = datetime.fromisoformat(inspection['updated_at'])
    
    return inspection

@api_router.put("/inspections/{inspection_id}", response_model=CarInspection)
async def update_inspection(inspection_id: str, update_data: CarInspectionUpdate):
    inspection = await db.inspections.find_one({"id": inspection_id}, {"_id": 0})
    
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    update_dict['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    await db.inspections.update_one({"id": inspection_id}, {"$set": update_dict})
    
    updated_inspection = await db.inspections.find_one({"id": inspection_id}, {"_id": 0})
    
    if isinstance(updated_inspection['created_at'], str):
        updated_inspection['created_at'] = datetime.fromisoformat(updated_inspection['created_at'])
    if isinstance(updated_inspection['updated_at'], str):
        updated_inspection['updated_at'] = datetime.fromisoformat(updated_inspection['updated_at'])
    
    return updated_inspection

@api_router.delete("/inspections/{inspection_id}")
async def delete_inspection(inspection_id: str):
    result = await db.inspections.delete_one({"id": inspection_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    return {"message": "Inspection deleted successfully"}

@api_router.post("/inspections/{inspection_id}/photos", response_model=PhotoUploadResponse)
async def upload_photo(inspection_id: str, file: UploadFile = File(...)):
    inspection = await db.inspections.find_one({"id": inspection_id}, {"_id": 0})
    
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    path = f"{APP_NAME}/uploads/{inspection_id}/{uuid.uuid4()}.{ext}"
    
    data = await file.read()
    result = put_object(path, data, file.content_type or "image/jpeg")
    
    await db.inspections.update_one(
        {"id": inspection_id},
        {"$push": {"photos": result["path"]}}
    )
    
    return PhotoUploadResponse(photo_url=f"/api/photos/{result['path']}", path=result["path"])

@api_router.get("/photos/{path:path}")
async def get_photo(path: str, authorization: str = Header(None), auth: str = Query(None)):
    try:
        data, content_type = get_object(path)
        return Response(content=data, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Photo not found")

@api_router.get("/download/project")
async def download_project():
    """Endpoint temporal para descargar el proyecto completo"""
    file_path = Path("/tmp/car-inspection-pro.tar.gz")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return Response(
        content=file_path.read_bytes(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": "attachment; filename=car-inspection-pro.tar.gz"
        }
    )

@api_router.get("/download/railway-backend")
async def download_railway_backend():
    """Descargar solo el backend preparado para Railway"""
    file_path = Path("/tmp/railway-backend.tar.gz")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return Response(
        content=file_path.read_bytes(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": "attachment; filename=railway-backend.tar.gz"
        }
    )

@api_router.get("/inspections/{inspection_id}/pdf")
async def generate_pdf_report(inspection_id: str):
    inspection = await db.inspections.find_one({"id": inspection_id}, {"_id": 0})
    
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#DC2626'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#DC2626'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=8
    )
    
    logo_path = Path(__file__).parent / 'assets' / 'logo.png'
    if logo_path.exists():
        logo = RLImage(str(logo_path), width=2*inch, height=2*inch)
        elements.append(logo)
        elements.append(Spacer(1, 0.3*inch))
    
    elements.append(Paragraph("REPORTE DE INSPECCIÓN", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    vehicle_info = [
        ['INFORMACIÓN DEL VEHÍCULO', ''],
        ['Marca:', inspection['brand']],
        ['Modelo:', inspection['model']],
        ['Año:', str(inspection['year'])],
        ['Kilometraje:', f"{inspection['mileage']:,} km"],
    ]
    
    vehicle_table = Table(vehicle_info, colWidths=[2*inch, 4*inch])
    vehicle_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F5F5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E0E0E0')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(vehicle_table)
    elements.append(Spacer(1, 0.3*inch))
    
    profit = inspection['estimated_sale_price'] - inspection['purchase_price']
    profit_color = colors.HexColor('#16A34A') if profit >= 0 else colors.HexColor('#EF4444')
    
    financial_info = [
        ['ANÁLISIS FINANCIERO', ''],
        ['Precio de Compra:', f"${inspection['purchase_price']:,.2f}"],
        ['Precio de Venta Estimado:', f"${inspection['estimated_sale_price']:,.2f}"],
        ['Ganancia Estimada:', f"${profit:,.2f}"],
    ]
    
    financial_table = Table(financial_info, colWidths=[2*inch, 4*inch])
    financial_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F5F5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E0E0E0')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TEXTCOLOR', (1, 3), (1, 3), profit_color),
        ('FONTNAME', (1, 3), (1, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 3), (1, 3), 14),
    ]))
    elements.append(financial_table)
    elements.append(Spacer(1, 0.3*inch))
    
    elements.append(Paragraph("INSPECCIÓN MECÁNICA", heading_style))
    mechanical = inspection.get('mechanical', {})
    mech_data = [
        ['Motor:', mechanical.get('engine', 'N/A')],
        ['Transmisión:', mechanical.get('transmission', 'N/A')],
        ['Frenos:', mechanical.get('brakes', 'N/A')],
        ['Suspensión:', mechanical.get('suspension', 'N/A')],
    ]
    if mechanical.get('notes'):
        mech_data.append(['Notas:', mechanical.get('notes', '')])
    
    mech_table = Table(mech_data, colWidths=[1.5*inch, 4.5*inch])
    mech_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5F5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E0E0E0')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(mech_table)
    elements.append(Spacer(1, 0.3*inch))
    
    elements.append(Paragraph("INSPECCIÓN COSMÉTICA", heading_style))
    cosmetic = inspection.get('cosmetic', {})
    cosm_data = [
        ['Pintura:', cosmetic.get('paint', 'N/A')],
        ['Interior:', cosmetic.get('interior', 'N/A')],
        ['Exterior:', cosmetic.get('exterior', 'N/A')],
    ]
    if cosmetic.get('notes'):
        cosm_data.append(['Notas:', cosmetic.get('notes', '')])
    
    cosm_table = Table(cosm_data, colWidths=[1.5*inch, 4.5*inch])
    cosm_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5F5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E0E0E0')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(cosm_table)
    elements.append(Spacer(1, 0.3*inch))
    
    if inspection.get('notes'):
        elements.append(Paragraph("NOTAS GENERALES", heading_style))
        elements.append(Paragraph(inspection['notes'], normal_style))
        elements.append(Spacer(1, 0.3*inch))
    
    if inspection.get('photos') and len(inspection['photos']) > 0:
        elements.append(Paragraph("GALERÍA DE FOTOS", heading_style))
        elements.append(Spacer(1, 0.2*inch))
        
        photos_data = []
        temp_row = []
        
        for idx, photo_path in enumerate(inspection['photos'][:6]):
            try:
                photo_data, _ = get_object(photo_path)
                photo_io = BytesIO(photo_data)
                
                img = RLImage(photo_io, width=2.3*inch, height=2.3*inch)
                temp_row.append(img)
                
                if len(temp_row) == 2:
                    photos_data.append(temp_row)
                    temp_row = []
                    
            except Exception as e:
                logger.error(f"Error loading photo {photo_path}: {e}")
                continue
        
        if temp_row:
            while len(temp_row) < 2:
                temp_row.append('')
            photos_data.append(temp_row)
        
        if photos_data:
            photos_table = Table(photos_data, colWidths=[2.5*inch, 2.5*inch])
            photos_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(photos_table)
            elements.append(Spacer(1, 0.3*inch))
            
            if len(inspection['photos']) > 6:
                elements.append(Paragraph(f"* Mostrando 6 de {len(inspection['photos'])} fotos totales", normal_style))
                elements.append(Spacer(1, 0.2*inch))
    
    created_date = inspection.get('created_at')
    if isinstance(created_date, str):
        created_date = datetime.fromisoformat(created_date)
    date_str = created_date.strftime('%d/%m/%Y') if created_date else 'N/A'
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"Reporte generado el {date_str} | PRO CARS", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"inspeccion_{inspection['brand']}_{inspection['model']}_{inspection['year']}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar para Railway - usar PORT si está disponible
port = int(os.environ.get('PORT', 8001))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup():
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()