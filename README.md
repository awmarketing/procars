# 🚗 Car Inspection Pro - Backend

Backend API para el sistema profesional de inspección de autos PRO CARS.

## 🛠️ Stack Tecnológico

- **Python 3.11** - FastAPI
- **MongoDB** - Base de datos
- **ReportLab** - Generación de PDFs
- **Emergent Storage** - Almacenamiento de fotos

## 🚀 Deploy en Railway

### Configuración Rápida

1. **Conecta este repositorio con Railway**
   - Ve a [railway.app](https://railway.app)
   - New Project → Deploy from GitHub repo
   - Selecciona `awmarketing/procars`

2. **Configura las variables de entorno:**

```env
MONGO_URL=mongodb+srv://usuario:password@cluster.mongodb.net/car_inspection
DB_NAME=car_inspection_prod
CORS_ORIGINS=*
EMERGENT_LLM_KEY=sk-emergent-0F21a5271D0B898DdA
```

3. **Railway detectará automáticamente:**
   - ✅ Python 3.11 (runtime.txt)
   - ✅ FastAPI (requirements.txt)
   - ✅ Comando de inicio (Procfile)

### MongoDB Atlas

Necesitas una base de datos MongoDB. Recomendamos MongoDB Atlas (GRATIS):

1. Crea cuenta en [mongodb.com/cloud/atlas](https://mongodb.com/cloud/atlas)
2. Crea cluster FREE (M0)
3. Crea usuario y contraseña
4. Permite acceso desde cualquier IP (0.0.0.0/0)
5. Copia connection string y úsalo en `MONGO_URL`

## 📚 Documentación

- `RAILWAY_DEPLOYMENT.md` - Guía completa de deployment
- API docs disponibles en `/docs` (Swagger UI)

## 🎨 Logo

El logo PRO CARS está incluido en `assets/logo.png` y se usa en los reportes PDF.

## 🔗 Endpoints Principales

- `GET /api/inspections` - Listar inspecciones
- `POST /api/inspections` - Crear inspección
- `GET /api/inspections/{id}` - Ver detalle
- `PUT /api/inspections/{id}` - Actualizar
- `DELETE /api/inspections/{id}` - Eliminar
- `POST /api/inspections/{id}/photos` - Subir fotos
- `GET /api/inspections/{id}/pdf` - Descargar PDF

## 📄 Licencia

© 2024 PRO CARS - Todos los derechos reservados
