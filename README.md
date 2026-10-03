# NEXUS CAR WASH · Sistema de gestión y fidelización

Aplicación web desarrollada con **Flask + Jinja2 + MongoDB**:
- **Landing page:** catálogo visual de servicios (con fotos y especificaciones técnicas), insumos de calidad y beneficios. Sin precios ni agendamiento de turnos.
- **Autenticación:** inicio de sesión y registro con botón azul *"Regístrate para obtener nuestros beneficios"*.
- **Panel del cliente:** fidelidad basada estrictamente en visitas (sin puntos):
  - 🎁 **4 visitas:** Un regalo especial de la casa.
  - 🚗 **8 visitas:** Un lavado premium totalmente gratis.
  - 🎂 **Cumpleaños:** *"El día de tu cumpleaños te tenemos un regalo especial"*.
  - Barra de progreso hacia las metas y tarjeta digital de socio con premios alcanzados.
- **Panel de administración:**
  - **Clientes y fidelidad:** listado completo con búsqueda en tiempo real, botón rápido `+ 1 Visita` para marcar cada visita en un clic, edición total de los datos de cada cliente (incluyendo corrección de visitas acumuladas) y **restablecimiento de contraseña** por olvido con generador automático.
  - **Servicios:** botón destacado `+ Agregar nuevo servicio` para crear servicios con sus especificaciones técnicas y foto subida a MongoDB, y botón `Editar completamente` en cada tarjeta de servicio para modificar nombre, categoría, etiqueta, ícono, descripción, especificaciones y foto.
  - **Logotipo:** visualización y reemplazo del logotipo oficial guardado en la base de datos MongoDB.

---

## Estructura del proyecto

```
├── main.py                     # Punto de entrada (verifica dependencias y arranca)
├── app.py                      # Rutas Flask + contexto global Jinja2
├── database.py                 # Capa de datos MongoDB (usuarios, visitas, servicios, insumos, logo)
├── cargar_logo.py              # CLI para subir el logo oficial a MongoDB
├── test_suite.py               # Suite de pruebas automatizadas
├── requirements.txt            # Dependencias (Flask, PyMongo, Werkzeug)
├── templates/
│   ├── base.html               # Header (logo oficial + NEXUS CAR WASH), WhatsApp e Instagram flotantes
│   ├── macros.html             # Tarjetas reutilizables de servicios, productos y beneficios
│   ├── _admin_nav.html         # Pestañas de navegación del panel de administración
│   ├── index.html              # Landing / catálogo puro sin precios ni turnos
│   ├── login.html              # Login con botón azul destacado de registro
│   ├── register.html           # Registro obligatorio (nombre, usuario, clave, nacimiento)
│   ├── client_dashboard.html   # Panel del cliente (visitas, metas 4v y 8v, regalos, cumpleaños)
│   ├── admin_dashboard.html    # Panel admin: tabla de clientes, contador de visitas y fidelidad rápida
│   ├── edit_client.html        # Edición total del cliente + visitas manuales + restablecer clave
│   ├── admin_services.html     # Panel admin: catálogo con botones '+ Agregar nuevo servicio' y 'Editar completamente'
│   ├── service_form.html       # Formulario completo: especificaciones técnicas y subida de foto a MongoDB
│   ├── admin_logo.html         # Panel admin: visor y subida del logo oficial
│   └── error.html              # Páginas de error 404 y 500
└── static/
    ├── css/styles.css          # Diseño blanco limpio con paleta corporativa del logo (azul, rojo, negro)
    ├── js/main.js              # JS: filtros, vista previa de fotos en vivo, generador de contraseñas
    └── img/nexus-logo.svg      # Logotipo oficial vectorial de respaldo
```

---

## Puesta en marcha

1. **Asegúrate de que MongoDB esté activo** en `mongodb://localhost:27017/`.
   > *Nota:* Si MongoDB no estuviera corriendo, la aplicación usa automáticamente una base de datos en memoria (`mongomock`) para que puedas probarla sin interrupciones.
2. **Instala dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Inicia el servidor**:
   ```bash
   python main.py
   ```
4. Abre tu navegador en **<http://127.0.0.1:5000>**.

---

### Cuentas de demostración

| Rol | Usuario | Contraseña | Detalle |
|---|---|---|---|
| **Administrador** | `admin` | `admin123` | Acceso completo a clientes, servicios y logo |
| **Cliente** | `carlos92` | `cliente123` | 5 visitas acumuladas (regalo de 4v desbloqueado) y cumpleaños hoy |
| **Cliente** | `mariag` | `cliente123` | 2 visitas (a 2 de su regalo especial) |
| **Cliente** | `lucas_v8` | `cliente123` | 9 visitas (regalo de 4v y lavado gratis de 8v desbloqueados) |

---

## Funcionalidades principales

### 1. Fidelidad exclusivamente por visitas (sin puntos)
- **4 visitas:** Desbloquea un regalo especial de la casa.
- **8 visitas:** Desbloquea un servicio de lavado completo totalmente gratis.
- **Cumpleaños:** Notificación activa *"El día de tu cumpleaños te tenemos un regalo especial"*.
- **Admin `+ 1 Visita`:** En la tabla de clientes o dentro de su ficha, el administrador suma una visita en un solo clic, con historial detallado (fecha, servicio realizado y usuario admin que lo registró).

### 2. Gestión total de clientes y contraseñas
- Modificación de cualquier dato: nombre completo, nombre de usuario, fecha de nacimiento, teléfono y rol.
- Corrección manual del contador de visitas si fuera necesario.
- **Restablecer contraseña:** Si el cliente la olvida, el administrador puede escribir una nueva contraseña o presionar **"Generar"** para crear una contraseña segura al instante.

### 3. Gestión de servicios (Crear y Editar completamente)
- **Botón `+ Agregar nuevo servicio`:** Permite cargar un servicio nuevo con su nombre, categoría, etiqueta distintiva, ícono, descripción detallada, especificaciones técnicas (una por línea) y su foto (subida a MongoDB o por URL).
- **Botón `Editar completamente`:** Disponible en cada tarjeta de servicio para actualizar cualquier detalle o cambiar su foto en cualquier momento.

### 4. Gestión de productos e insumos (Crear, Editar y Fotos)
- **Pestaña Productos:** Listado visual completo de todos los insumos de alta gama.
- **Botón `+ Agregar nuevo producto`:** Permite registrar productos con nombre, marca fabricante, categoría, sello eco-friendly, ícono, descripción detallada, beneficios clave (uno por línea) y foto subida directamente a MongoDB.
- **Botón `Editar completamente` y `Eliminar`:** Control total sobre cada insumo utilizado.

---

## Despliegue en Render (paso a paso)

1. **Sube tu código a GitHub** en un repositorio (público o privado).
2. **Crea tu base de datos en MongoDB Atlas** (gratuita):
   - Ve a [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) y crea un cluster M0 Free.
   - En *Database Access*, crea un usuario y contraseña.
   - En *Network Access*, añade `0.0.0.0/0` (permitir acceso desde cualquier IP).
   - En *Database → Connect*, copia la URI `mongodb+srv://...`.
3. **Crea el Web Service en Render**:
   - Inicia sesión en [render.com](https://render.com) y haz clic en **New + → Web Service**.
   - Conecta tu repositorio de GitHub.
   - Configura los siguientes campos:
     - **Name:** `nexus-car-wash`
     - **Region:** Selecciona la más cercana (ej. Ohio, Oregon o Frankfurt).
     - **Branch:** `main`
     - **Runtime:** `Python 3`
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `gunicorn app:app`
     - **Instance Type:** `Free`
4. **Configura las Variables de Entorno (Environment Variables)**:
   - `MONGO_URI`: Tu cadena de conexión de MongoDB Atlas (ej. `mongodb+srv://usuario:password@cluster0.abcde.mongodb.net/nexus_car_wash?retryWrites=true&w=majority`).
   - `MONGO_DB_NAME`: `nexus_car_wash`
   - `SECRET_KEY`: Una cadena segura aleatoria para las sesiones.
   - `NEXUS_WHATSAPP`: Número de WhatsApp en formato internacional (sin `+`).
   - `NEXUS_INSTAGRAM`: Enlace a tu perfil de Instagram.
5. Haz clic en **Create Web Service**. ¡Listo! Render compilará e iniciará automáticamente tu aplicación con Gunicorn.
