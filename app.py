"""
NEXUS CAR WASH - Servidor Flask (plantillas Jinja2 + MongoDB).

Rutas públicas:
    /                                   Landing: catálogo, productos y beneficios (sin precios ni turnos)
    /login, /registro, /logout          Autenticación
    /logo                               Logotipo oficial guardado en MongoDB
    /servicios/<id>/imagen              Foto de un servicio guardada en MongoDB

Panel del cliente:
    /cliente                            client_dashboard (puntos, visitas, beneficios e historial)

Panel del administrador:
    /admin                              Clientes: listado, búsqueda y "+ Visita" rápida
    /admin/clientes/<id>/editar         Edición total del cliente (incluye restablecer contraseña) + fidelidad
    /admin/clientes/<id>/fidelidad      Registrar visita / puntos extra / canje / ajuste (POST)
    /admin/clientes/<id>/eliminar       Eliminar cliente (POST)
    /admin/servicios                    Catálogo: listado de servicios
    /admin/servicios/nuevo              Crear servicio (con foto)
    /admin/servicios/<id>/editar        Editar descripción, datos y foto
    /admin/servicios/<id>/eliminar      Eliminar servicio (POST)
    /admin/logo                         Ver y reemplazar el logotipo oficial
"""

import os
import re
from datetime import date, datetime, timezone
from functools import wraps
from urllib.parse import quote

from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for

import database as db

# ---------------------------------------------------------------------------
# Configuración de marca, contacto y fidelidad (editable con variables de entorno)
# ---------------------------------------------------------------------------
BRAND_NAME = "NEXUS CAR WASH"
WHATSAPP_NUMBER = os.environ.get("NEXUS_WHATSAPP", "5491100000000")  # Formato internacional, sin "+" ni espacios
WHATSAPP_MESSAGE = os.environ.get("NEXUS_WHATSAPP_MSG", "¡Hola NEXUS CAR WASH! Quiero hacer una consulta.")
INSTAGRAM_URL = os.environ.get("NEXUS_INSTAGRAM", "https://www.instagram.com/nexuscarwash/")

# Metas de fidelidad basadas exclusivamente en visitas (sin puntos)
VISITS_FOR_GIFT = db.VISITS_FOR_GIFT          # 4 visitas = un regalo especial
VISITS_FOR_FREE_WASH = db.VISITS_FOR_FREE_WASH  # 8 visitas = un lavado gratis
BIRTHDAY_TEXT = "El día de tu cumpleaños te tenemos un regalo especial."

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_SERVICE_IMAGE_BYTES = 5 * 1024 * 1024
USERNAME_RE = re.compile(r"^[a-z0-9._]{3,30}$")

# Beneficios de ser cliente registrado (landing y registro)
BENEFITS = [
    {"icon": "fa-solid fa-cake-candles", "title": "Regalo de cumpleaños",
     "text": BIRTHDAY_TEXT},
    {"icon": "fa-solid fa-gift", "title": f"{VISITS_FOR_GIFT} visitas = Un regalo",
     "text": f"Al alcanzar {VISITS_FOR_GIFT} visitas te entregamos un regalo especial de la casa."},
    {"icon": "fa-solid fa-car-side", "title": f"{VISITS_FOR_FREE_WASH} visitas = Lavado gratis",
     "text": f"Al alcanzar {VISITS_FOR_FREE_WASH} visitas obtienes un lavado premium totalmente gratis."},
]

# Íconos disponibles para los servicios (formulario del admin)
SERVICE_ICONS = [
    ("fa-solid fa-soap", "Espuma / lavado"),
    ("fa-solid fa-wand-magic-sparkles", "Brillo / encerado"),
    ("fa-solid fa-couch", "Tapicería"),
    ("fa-solid fa-shield-halved", "Protección / cerámico"),
    ("fa-solid fa-hand-sparkles", "Cuero / detalle"),
    ("fa-solid fa-gears", "Motor"),
    ("fa-solid fa-spray-can-sparkles", "Pulverizado"),
    ("fa-solid fa-droplet", "Agua"),
    ("fa-solid fa-car", "Auto"),
    ("fa-solid fa-star", "Destacado"),
]

# Íconos disponibles para los productos (formulario del admin)
PRODUCT_ICONS = [
    ("fa-solid fa-flask", "Frasco / químico"),
    ("fa-solid fa-shield-heart", "Protección / cera"),
    ("fa-solid fa-spray-can-sparkles", "Pulverizador"),
    ("fa-solid fa-droplet", "Shampoo / gota"),
    ("fa-solid fa-gem", "Cuarzo / cerámico"),
    ("fa-solid fa-bottle-droplet", "Botella / insumo"),
    ("fa-solid fa-hand-sparkles", "Cuidado artesanal"),
    ("fa-solid fa-leaf", "Ecológico"),
    ("fa-solid fa-wand-magic-sparkles", "Brillo"),
]
MAX_PRODUCT_IMAGE_BYTES = 5 * 1024 * 1024

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "nexus-car-wash-dev-key-cambiar-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # Límite de subida (logo y fotos)

db.init_db()


# ---------------------------------------------------------------------------
# Usuario actual y contexto global de plantillas
# ---------------------------------------------------------------------------

@app.before_request
def load_current_user():
    """Carga el usuario logueado en `g.user` (o None) en cada request."""
    g.user = None
    if request.endpoint == "static":
        return
    user_id = session.get("user_id")
    if user_id:
        g.user = db.get_user_by_id(user_id)
        if g.user is None:  # El usuario fue eliminado: se limpia la sesión
            session.clear()


def _build_logo_context():
    """Consulta el logo en MongoDB y arma la info que necesitan las plantillas."""
    meta = None
    try:
        meta = db.get_logo_meta()
    except Exception:  # Si la BD falla, la página igual se renderiza con el logo de respaldo
        app.logger.exception("No se pudo leer el logo desde MongoDB")

    if meta:
        return {
            "url": url_for("logo_image", v=meta["version"]),
            "alt": f"Logotipo oficial de {BRAND_NAME}",
            "from_db": True,
            "filename": meta.get("filename", ""),
        }
    return {
        "url": url_for("static", filename="img/nexus-logo.svg"),
        "alt": f"Logotipo de {BRAND_NAME}",
        "from_db": False,
        "filename": "",
    }


@app.context_processor
def inject_layout_context():
    """Variables disponibles en todas las plantillas (header, footer, botones flotantes)."""
    return {
        "brand_name": BRAND_NAME,
        "logo": _build_logo_context(),
        "current_user": g.get("user"),
        "whatsapp_url": f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(WHATSAPP_MESSAGE)}",
        "instagram_url": INSTAGRAM_URL,
        "current_year": datetime.now().year,
        "using_mock_db": db.USING_MOCK,
        "admin_section": "",  # Las vistas del admin lo sobrescriben para marcar la pestaña activa
    }


def _to_local(value):
    """MongoDB devuelve fechas UTC sin zona horaria: se pasan a la hora local."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone()


@app.template_filter("fecha")
def format_date(value):
    """Formatea 'YYYY-MM-DD' o datetime como 'DD/MM/YYYY'."""
    if not value:
        return "—"
    if isinstance(value, datetime):
        return _to_local(value).strftime("%d/%m/%Y")
    parsed = db.parse_birth_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else str(value)


@app.template_filter("fechahora")
def format_datetime(value):
    """Formatea un datetime como 'DD/MM/YYYY HH:MM' (hora local)."""
    if not isinstance(value, datetime):
        return "—"
    return _to_local(value).strftime("%d/%m/%Y %H:%M")


# ---------------------------------------------------------------------------
# Decoradores de acceso
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Inicia sesión para continuar.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Inicia sesión con una cuenta de administrador.", "info")
            return redirect(url_for("login", next=request.path))
        if g.user["role"] != "admin":
            flash("No tienes permisos para acceder al panel de administración.", "error")
            return redirect(url_for("client_dashboard"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redirect_for_role(user):
    return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "client_dashboard"))


def _is_safe_next(target):
    return bool(target) and target.startswith("/") and not target.startswith("//")


def _validate_user_form(form, require_password, exclude_id=None, admin_fields=False):
    """Valida los datos de registro/edición. Devuelve (datos_limpios, lista_errores)."""
    errors = []
    full_name = form.get("full_name", "").strip()
    username = form.get("username", "").strip().lower()
    password = form.get("password", "")
    birth_date = form.get("birth_date", "").strip()
    phone = form.get("phone", "").strip()

    if len(full_name) < 3:
        errors.append("Ingresa el nombre completo.")
    if not USERNAME_RE.match(username):
        errors.append("El usuario debe tener entre 3 y 30 caracteres: letras, números, punto o guion bajo.")
    elif db.username_exists(username, exclude_id=exclude_id):
        errors.append("Ese nombre de usuario ya está en uso.")
    if require_password or password:
        if len(password) < 6:
            errors.append("La contraseña debe tener al menos 6 caracteres.")

    parsed = db.parse_birth_date(birth_date)
    if not parsed:
        errors.append("Ingresa una fecha de nacimiento válida.")
    elif parsed.date() >= date.today() or parsed.year < 1900:
        errors.append("La fecha de nacimiento no es válida.")

    data = {
        "full_name": full_name,
        "username": username,
        "password": password,
        "birth_date": birth_date,
        "phone": phone,
    }

    if admin_fields:
        role = form.get("role", "client")
        if role not in ("client", "admin"):
            errors.append("Rol inválido.")
        data["role"] = role

        if "visits" in form and form.get("visits") != "":
            try:
                data["visits"] = max(0, int(form.get("visits", 0)))
            except (ValueError, TypeError):
                errors.append("La cantidad de visitas debe ser un número entero mayor o igual a 0.")

    return data, errors


def _validate_service_form(form):
    """Valida el formulario de servicios. Devuelve (datos_limpios, lista_errores)."""
    errors = []
    valid_icons = {icon for icon, _label in SERVICE_ICONS}
    icon = form.get("icon", "")
    image_url = form.get("image_url", "").strip()
    data = {
        "name": form.get("name", "").strip(),
        "category": form.get("category", "").strip(),
        "description": form.get("description", "").strip(),
        "badge": form.get("badge", "").strip()[:30],
        "icon": icon if icon in valid_icons else "fa-solid fa-car",
        "features": [line.strip() for line in form.get("features", "").splitlines() if line.strip()][:8],
        "image_url": image_url,
    }
    if len(data["name"]) < 3:
        errors.append("El nombre del servicio debe tener al menos 3 caracteres.")
    if not data["category"]:
        errors.append("Ingresa una categoría (ej: Lavado exterior).")
    if len(data["description"]) < 10:
        errors.append("La descripción debe tener al menos 10 caracteres.")
    if image_url and not image_url.startswith(("http://", "https://")):
        errors.append("El enlace de la foto debe empezar con http:// o https://")
    return data, errors


def _validate_product_form(form):
    """Valida el formulario de insumos/productos. Devuelve (datos_limpios, lista_errores)."""
    errors = []
    valid_icons = {icon for icon, _label in PRODUCT_ICONS}
    icon = form.get("icon", "")
    image_url = form.get("image_url", "").strip()
    data = {
        "name": form.get("name", "").strip(),
        "brand": form.get("brand", "").strip(),
        "category": form.get("category", "").strip(),
        "description": form.get("description", "").strip(),
        "eco": form.get("eco") == "1",
        "icon": icon if icon in valid_icons else "fa-solid fa-flask",
        "benefits": [line.strip() for line in form.get("benefits", "").splitlines() if line.strip()][:8],
        "image_url": image_url,
    }
    if len(data["name"]) < 3:
        errors.append("El nombre del producto debe tener al menos 3 caracteres.")
    if not data["brand"]:
        errors.append("Ingresa la marca del producto (ej: Meguiar's, Koch-Chemie).")
    if not data["category"]:
        errors.append("Ingresa una categoría (ej: Protección de pintura).")
    if len(data["description"]) < 10:
        errors.append("La descripción debe tener al menos 10 caracteres.")
    if image_url and not image_url.startswith(("http://", "https://")):
        errors.append("El enlace de la foto debe empezar con http:// o https://")
    return data, errors


def _read_uploaded_image(file, max_bytes):
    """Lee una imagen subida. Devuelve (bytes, content_type, error). Sin archivo -> (None, None, None)."""
    if not file or not file.filename:
        return None, None, None
    content_type = (file.mimetype or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        return None, None, "Formato de imagen no permitido. Usa PNG, JPG, WEBP o SVG."
    data = file.read()
    if not data:
        return None, None, "El archivo de imagen está vacío."
    if len(data) > max_bytes:
        return None, None, f"La imagen debe pesar como máximo {max_bytes // (1024 * 1024)} MB."
    return data, content_type, None


def _image_response(data, content_type):
    """Respuesta HTTP segura para imágenes guardadas en MongoDB."""
    response = Response(data, mimetype=content_type)
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Evita que un SVG subido ejecute scripts si se abre directamente
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    return response


def _catalog():
    """Servicios con `image_src` resuelto: foto subida (MongoDB) > enlace externo > sin foto."""
    services = db.get_services()
    for service in services:
        service["image_src"] = _service_image_src(service)
    return services


def _service_image_src(service):
    if service["has_image"]:
        return url_for("service_image", service_id=service["id"], v=service["image_version"])
    return service["image_url"]


def _catalog_products():
    """Productos con `image_src` resuelto: foto subida (MongoDB) > enlace externo > sin foto."""
    products = db.get_products()
    for product in products:
        product["image_src"] = _product_image_src(product)
    return products


def _product_image_src(product):
    if product.get("has_image"):
        return url_for("product_image", product_id=product["id"], v=product.get("image_version", 0))
    return product.get("image_url", "")


def _build_perks(user):
    """Beneficios del cliente: regalo de cumpleaños + premio de 4 visitas (regalo) + premio de 8 visitas (lavado gratis)."""
    birthday_today = user["is_birthday_today"]
    visits = user["visits"]
    has_gift = user["has_gift"]
    has_free_wash = user["has_free_wash"]

    return [
        {
            "icon": "fa-solid fa-cake-candles",
            "title": "Regalo de cumpleaños",
            "description": BIRTHDAY_TEXT,
            "status": "¡Hoy es tu día! Pasa a retirarlo" if birthday_today
            else (f"Te esperamos el {user['birthday_label']}" if user["birthday_label"] else "Disponible el día de tu cumpleaños"),
            "unlocked": birthday_today,
            "highlight": birthday_today,
        },
        {
            "icon": "fa-solid fa-gift",
            "title": f"Premio {VISITS_FOR_GIFT} visitas: Regalo de la casa",
            "description": f"Completa {VISITS_FOR_GIFT} visitas en el lavadero y recibe un regalo especial exclusivo.",
            "status": "¡Premio desbloqueado! Pasa a retirarlo" if has_gift
            else f"Te faltan {VISITS_FOR_GIFT - visits} visita{'s' if VISITS_FOR_GIFT - visits != 1 else ''}",
            "unlocked": has_gift,
            "highlight": has_gift and not has_free_wash,
        },
        {
            "icon": "fa-solid fa-car-side",
            "title": f"Premio {VISITS_FOR_FREE_WASH} visitas: Lavado gratis",
            "description": f"Alcanza {VISITS_FOR_FREE_WASH} visitas y obtén un servicio de lavado completo totalmente sin cargo.",
            "status": "¡Lavado gratis desbloqueado! Listo para usar" if has_free_wash
            else f"Te faltan {VISITS_FOR_FREE_WASH - visits} visita{'s' if VISITS_FOR_FREE_WASH - visits != 1 else ''}",
            "unlocked": has_free_wash,
            "highlight": has_free_wash,
        },
    ]


# ---------------------------------------------------------------------------
# Rutas públicas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Landing: catálogo visual, productos y beneficios. Sin precios ni turnos."""
    return render_template("index.html", services=_catalog(), products=_catalog_products(), benefits=BENEFITS)


@app.route("/logo")
def logo_image():
    """Sirve el logotipo oficial guardado en MongoDB."""
    logo = db.get_logo()
    if not logo:
        return redirect(url_for("static", filename="img/nexus-logo.svg"))
    return _image_response(logo["data"], logo["content_type"])


@app.route("/servicios/<service_id>/imagen")
def service_image(service_id):
    """Sirve la foto de un servicio guardada en MongoDB."""
    image = db.get_service_image(service_id)
    if not image:
        abort(404)
    return _image_response(image["data"], image["content_type"])


@app.route("/productos/<product_id>/imagen")
def product_image(product_id):
    """Sirve la foto de un producto/insumo guardada en MongoDB."""
    image = db.get_product_image(product_id)
    if not image:
        abort(404)
    return _image_response(image["data"], image["content_type"])


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return _redirect_for_role(g.user)

    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.authenticate(username, password) if username and password else None

        if user:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"¡Hola, {user['first_name']}! Qué bueno verte de nuevo.", "success")
            next_url = request.args.get("next", "")
            if _is_safe_next(next_url) and (user["role"] == "admin" or not next_url.startswith("/admin")):
                return redirect(next_url)
            return _redirect_for_role(user)

        flash("Usuario o contraseña incorrectos.", "error")

    return render_template("login.html", username=username)


@app.route("/registro", methods=["GET", "POST"])
def register():
    if g.user:
        return _redirect_for_role(g.user)

    form = {}
    if request.method == "POST":
        form = request.form
        data, errors = _validate_user_form(request.form, require_password=True)
        if not errors:
            try:
                user_id = db.create_user(**data)
            except ValueError as exc:
                errors.append(str(exc))
            else:
                session.clear()
                session["user_id"] = user_id
                flash(f"¡Bienvenido a {BRAND_NAME}! Tu cuenta fue creada exitosamente.", "success")
                return redirect(url_for("client_dashboard"))
        for error in errors:
            flash(error, "error")

    return render_template(
        "register.html",
        form=form,
        today=date.today().isoformat(),
        benefits=BENEFITS,
    )


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Cerraste sesión correctamente. ¡Te esperamos pronto!", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Panel del cliente
# ---------------------------------------------------------------------------

@app.route("/cliente")
@login_required
def client_dashboard():
    """Panel del cliente. Se pasan TODAS las variables que usa la plantilla."""
    user = g.user
    return render_template(
        "client_dashboard.html",
        user=user,
        visits=user["visits"],
        is_birthday_today=user["is_birthday_today"],
        perks=_build_perks(user),
        history=user["history"][:8],
        services=_catalog(),
        products=_catalog_products(),
        visits_for_gift=VISITS_FOR_GIFT,
        visits_for_free_wash=VISITS_FOR_FREE_WASH,
    )


# ---------------------------------------------------------------------------
# Panel del administrador: CLIENTES Y FIDELIDAD
# ---------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template(
        "admin_dashboard.html",
        admin_section="clientes",
        clients=db.get_all_users(),
        stats=db.get_dashboard_stats(),
        visits_for_gift=VISITS_FOR_GIFT,
        visits_for_free_wash=VISITS_FOR_FREE_WASH,
    )


@app.route("/admin/clientes/<user_id>/editar", methods=["GET", "POST"])
@admin_required
def edit_client(user_id):
    """Edición total: nombre, usuario, contraseña, fecha de nacimiento, teléfono, rol y visitas."""
    client = db.get_user_by_id(user_id)
    if not client:
        flash("El cliente no existe o fue eliminado.", "error")
        return redirect(url_for("admin_dashboard"))

    form = client
    if request.method == "POST":
        form = request.form
        data, errors = _validate_user_form(request.form, require_password=False,
                                           exclude_id=user_id, admin_fields=True)
        if client["id"] == g.user["id"] and data.get("role") != "admin":
            errors.append("No puedes quitarte a ti mismo el rol de administrador.")

        if not errors:
            try:
                db.update_user(user_id, **data)
            except ValueError as exc:
                errors.append(str(exc))
            else:
                message = f"Datos de {data['full_name']} actualizados correctamente."
                if data.get("password"):
                    message += " La contraseña fue restablecida: compártela con el cliente."
                flash(message, "success")
                return redirect(url_for("edit_client", user_id=user_id))
        for error in errors:
            flash(error, "error")

    return render_template(
        "edit_client.html",
        admin_section="clientes",
        client=db.get_user_by_id(user_id),
        form=form,
        today=date.today().isoformat(),
        visits_for_gift=VISITS_FOR_GIFT,
        visits_for_free_wash=VISITS_FOR_FREE_WASH,
    )


@app.route("/admin/clientes/<user_id>/visita", methods=["POST"])
@app.route("/admin/clientes/<user_id>/fidelidad", methods=["POST"])
@admin_required
def add_loyalty(user_id):
    """Marca la fidelidad del cliente: suma +1 visita y actualiza el historial."""
    client = db.get_user_by_id(user_id)
    if not client:
        flash("Cliente no encontrado.", "error")
        return redirect(url_for("admin_dashboard"))

    note = request.form.get("note", "Visita al lavadero")
    try:
        new_total = db.add_visit(user_id, note=note, by=g.user["username"])
    except Exception as exc:
        flash(str(exc), "error")
    else:
        msg = f"¡Visita registrada para {client['full_name']}! Total acumulado: {new_total} visita{'s' if new_total != 1 else ''}."
        if new_total == VISITS_FOR_GIFT:
            msg += " 🎁 ¡Alcanzó 4 visitas y desbloqueó su regalo especial!"
        elif new_total == VISITS_FOR_FREE_WASH:
            msg += " 🚗 ¡Alcanzó 8 visitas y ganó un lavado gratis!"
        flash(msg, "success")

    if request.form.get("next") == "edit":
        return redirect(url_for("edit_client", user_id=user_id, _anchor="fidelidad"))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/clientes/<user_id>/eliminar", methods=["POST"])
@admin_required
def delete_client(user_id):
    if user_id == g.user["id"]:
        flash("No puedes eliminar tu propia cuenta.", "error")
        return redirect(url_for("admin_dashboard"))
    client = db.get_user_by_id(user_id)
    if client and db.delete_user(user_id):
        flash(f"Se eliminó a {client['full_name']}.", "success")
    else:
        flash("No se encontró el cliente.", "error")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Panel del administrador: SERVICIOS (descripción y fotos)
# ---------------------------------------------------------------------------

@app.route("/admin/servicios")
@admin_required
def admin_services():
    return render_template("admin_services.html", admin_section="servicios", services=_catalog())


@app.route("/admin/servicios/nuevo", methods=["GET", "POST"])
@app.route("/admin/servicios/<service_id>/editar", methods=["GET", "POST"])
@admin_required
def edit_service(service_id=None):
    """Crea o edita un servicio: nombre, categoría, descripción, características, ícono y foto."""
    service = None
    if service_id:
        service = db.get_service(service_id)
        if not service:
            flash("El servicio no existe o fue eliminado.", "error")
            return redirect(url_for("admin_services"))
        service["image_src"] = _service_image_src(service)

    form = service or {"icon": SERVICE_ICONS[0][0]}
    features_text = "\n".join(service["features"]) if service else ""

    if request.method == "POST":
        form = request.form
        features_text = request.form.get("features", "")
        data, errors = _validate_service_form(request.form)
        image, content_type, image_error = _read_uploaded_image(request.files.get("image"), MAX_SERVICE_IMAGE_BYTES)
        if image_error:
            errors.append(image_error)

        if not errors:
            if service:
                db.update_service(service_id, data)
                target_id = service_id
            else:
                target_id = db.create_service(data)
            if image:
                db.save_service_image(target_id, image, content_type)
            elif service and request.form.get("remove_image"):
                db.remove_service_image(target_id)
            flash(f"Servicio \"{data['name']}\" guardado correctamente.", "success")
            return redirect(url_for("admin_services"))
        for error in errors:
            flash(error, "error")

    return render_template(
        "service_form.html",
        admin_section="servicios",
        service=service,
        form=form,
        features_text=features_text,
        icons=SERVICE_ICONS,
    )


@app.route("/admin/servicios/<service_id>/eliminar", methods=["POST"])
@admin_required
def delete_service(service_id):
    service = db.get_service(service_id)
    if service and db.delete_service(service_id):
        flash(f"Se eliminó el servicio \"{service['name']}\".", "success")
    else:
        flash("No se encontró el servicio.", "error")
    return redirect(url_for("admin_services"))


# ---------------------------------------------------------------------------
# Panel del administrador: PRODUCTOS E INSUMOS UTILIZADOS (descripción y fotos)
# ---------------------------------------------------------------------------

@app.route("/admin/productos")
@admin_required
def admin_products():
    return render_template("admin_products.html", admin_section="productos", products=_catalog_products())


@app.route("/admin/productos/nuevo", methods=["GET", "POST"])
@app.route("/admin/productos/<product_id>/editar", methods=["GET", "POST"])
@admin_required
def edit_product(product_id=None):
    """Crea o edita un producto: nombre, marca, categoría, descripción, beneficios, eco, ícono y foto."""
    product = None
    if product_id:
        product = db.get_product(product_id)
        if not product:
            flash("El producto no existe o fue eliminado.", "error")
            return redirect(url_for("admin_products"))
        product["image_src"] = _product_image_src(product)

    form = product or {"icon": PRODUCT_ICONS[0][0], "eco": False}
    benefits_text = "\n".join(product["benefits"]) if product else ""

    if request.method == "POST":
        form = request.form
        benefits_text = request.form.get("benefits", "")
        data, errors = _validate_product_form(request.form)
        image, content_type, image_error = _read_uploaded_image(request.files.get("image"), MAX_PRODUCT_IMAGE_BYTES)
        if image_error:
            errors.append(image_error)

        if not errors:
            if product:
                db.update_product(product_id, data)
                target_id = product_id
            else:
                target_id = db.create_product(data)
            if image:
                db.save_product_image(target_id, image, content_type)
            elif product and request.form.get("remove_image"):
                db.remove_product_image(target_id)
            flash(f"Producto \"{data['name']}\" guardado correctamente.", "success")
            return redirect(url_for("admin_products"))
        for error in errors:
            flash(error, "error")

    return render_template(
        "product_form.html",
        admin_section="productos",
        product=product,
        form=form,
        benefits_text=benefits_text,
        icons=PRODUCT_ICONS,
    )


@app.route("/admin/productos/<product_id>/eliminar", methods=["POST"])
@admin_required
def delete_product(product_id):
    product = db.get_product(product_id)
    if product and db.delete_product(product_id):
        flash(f"Se eliminó el producto \"{product['name']}\".", "success")
    else:
        flash("No se encontró el producto.", "error")
    return redirect(url_for("admin_products"))


# ---------------------------------------------------------------------------
# Panel del administrador: LOGO
# ---------------------------------------------------------------------------

@app.route("/admin/logo", methods=["GET", "POST"])
@admin_required
def upload_logo():
    """Muestra y reemplaza el logotipo oficial (guardado en MongoDB)."""
    if request.method == "POST":
        data, content_type, error = _read_uploaded_image(request.files.get("logo"), MAX_LOGO_BYTES)
        if error:
            flash(error, "error")
        elif not data:
            flash("Selecciona un archivo de imagen.", "error")
        else:
            db.save_logo(data, content_type, request.files["logo"].filename)
            flash("Logotipo actualizado. Ya se muestra en todas las páginas.", "success")
        return redirect(url_for("upload_logo"))
    return render_template("admin_logo.html", admin_section="logo")


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, title="Página no encontrada",
                           message="La página que buscas no existe o fue movida."), 404


@app.errorhandler(413)
def too_large(_error):
    flash("El archivo es demasiado grande.", "error")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.errorhandler(500)
def server_error(_error):
    return render_template("error.html", code=500, title="Error interno",
                           message="Ocurrió un problema inesperado. Intenta nuevamente en unos minutos."), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
