# Railway Deployment - Backend

## Variables de Entorno para Railway

Copia y pega estas variables en Railway:

```
MONGO_URL=mongodb+srv://usuario:password@cluster.mongodb.net/car_inspection
DB_NAME=car_inspection_prod
CORS_ORIGINS=*
EMERGENT_LLM_KEY=sk-emergent-0F21a5271D0B898DdA
PORT=8000
```

**Importante:** 
- Cambia el MONGO_URL por tu MongoDB Atlas URL (ver instrucciones abajo)
- El PORT lo maneja Railway automáticamente
- CORS_ORIGINS en producción debe ser tu dominio específico

## MongoDB Atlas Setup (5 minutos)

### 1. Crear cuenta en MongoDB Atlas
1. Ve a https://www.mongodb.com/cloud/atlas/register
2. Crea cuenta gratuita (FREE tier - 512MB)
3. Elige el proveedor más cercano (AWS o Google Cloud)

### 2. Crear Database
1. Click en "Build a Database"
2. Selecciona "FREE" (M0 Sandbox)
3. Elige región más cercana (ej: AWS - US East)
4. Click "Create"

### 3. Crear Usuario
1. Ve a "Database Access" (menú izquierdo)
2. Click "Add New Database User"
3. Crea usuario y contraseña (guárdalos)
4. Selecciona "Read and write to any database"
5. Click "Add User"

### 4. Permitir acceso desde cualquier IP
1. Ve a "Network Access" (menú izquierdo)
2. Click "Add IP Address"
3. Click "Allow Access from Anywhere" (0.0.0.0/0)
4. Click "Confirm"

### 5. Obtener Connection String
1. Ve a "Database" (menú izquierdo)
2. Click en "Connect" en tu cluster
3. Selecciona "Connect your application"
4. Copia el connection string:
   ```
   mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/
   ```
5. Reemplaza `<username>` y `<password>` con tus credenciales
6. Agrega el nombre de la base de datos al final:
   ```
   mongodb+srv://tuusuario:tupassword@cluster0.xxxxx.mongodb.net/car_inspection
   ```

Esta será tu variable MONGO_URL para Railway.
