"""
Capa de datos MongoDB para NEXUS CAR WASH.

Colecciones utilizadas:
    users     -> clientes y administradores
    services  -> catálogo visual de servicios (SIN precios ni turnos)
    products  -> insumos de alta gama utilizados en el lavadero
    assets    -> archivos binarios de la marca (logotipo oficial, _id = "logo")

Variables de entorno:
    MONGO_URI      (por defecto: mongodb://localhost:27017/)
    MONGO_DB_NAME  (por defecto: nexus_car_wash)
"""

import calendar
import os
from datetime import datetime, timezone

from bson import Binary, ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "nexus_car_wash")
DEFAULT_LOGO_PATH = os.path.join(BASE_DIR, "static", "img", "nexus-logo.svg")

# Metas de fidelidad basadas exclusivamente en visitas (sin puntos)
VISITS_FOR_GIFT = 4       # 4 visitas = un regalo especial
VISITS_FOR_FREE_WASH = 8  # 8 visitas = un lavado gratis

_client = None
_db = None
USING_MOCK = False  # True si se usa mongomock (datos en memoria)


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def get_db():
    """Devuelve la base de datos MongoDB (conexión perezosa y reutilizable).

    Lee la URI desde la variable de entorno `MONGO_URI`. Si se despliega en Render
    con MongoDB Atlas, se conectará automáticamente. Si MongoDB local no responde
    y está disponible `mongomock`, se usa una base en memoria para desarrollo.
    """
    global _client, _db, USING_MOCK
    if _db is not None:
        return _db

    uri = os.environ.get("MONGO_URI", "").strip() or "mongodb://localhost:27017/"
    db_name = os.environ.get("MONGO_DB_NAME", "").strip() or "nexus_car_wash"

    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=3500)
        _client.admin.command("ping")
        # Si la URI ya incluye el nombre de la base de datos (habitual en Atlas), la usamos
        try:
            default_db = _client.get_default_database()
            _db = default_db if default_db is not None else _client[db_name]
        except Exception:
            _db = _client[db_name]
    except Exception as exc:
        try:
            import mongomock
        except ImportError:
            raise RuntimeError(
                f"No se pudo conectar a MongoDB en {uri}. "
                "Asegúrate de definir la variable de entorno MONGO_URI correctamente en Render."
            ) from exc
        print(f"[!] MongoDB no disponible en {uri} -> usando base EN MEMORIA (mongomock).")
        print("    Para persistir datos en producción, define MONGO_URI con tu conexión a MongoDB Atlas.")
        _client = mongomock.MongoClient()
        USING_MOCK = True
        _db = _client[db_name]

    return _db


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def _to_object_id(value):
    """Convierte un string a ObjectId; devuelve None si no es válido."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def _is_duplicate_error(exc):
    """Detecta errores de clave duplicada (pymongo o mongomock)."""
    return isinstance(exc, DuplicateKeyError) or type(exc).__name__ == "DuplicateKeyError"


def parse_birth_date(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def is_birthday_month(birth_date):
    parsed = parse_birth_date(birth_date)
    return bool(parsed and parsed.month == datetime.now().month)


def is_birthday_today(birth_date):
    """True si hoy es el cumpleaños (los nacidos el 29/02 festejan el 28/02 en años no bisiestos)."""
    parsed = parse_birth_date(birth_date)
    if not parsed:
        return False
    today = datetime.now()
    if parsed.month == 2 and parsed.day == 29 and not calendar.isleap(today.year):
        return today.month == 2 and today.day == 28
    return parsed.month == today.month and parsed.day == today.day


def _serialize_user(doc):
    """Convierte un documento de MongoDB en un dict seguro para las plantillas.

    Nunca incluye el hash de la contraseña. Todas las claves que usan las
    plantillas están siempre presentes para evitar `UndefinedError`.
    La fidelidad se rige exclusivamente por visitas (4 = regalo, 8 = lavado gratis).
    """
    if not doc:
        return None
    birth = parse_birth_date(doc.get("birth_date", ""))
    visits = int(doc.get("visits", 0) or 0)

    # Estado de premios por visitas
    has_gift = visits >= VISITS_FOR_GIFT
    has_free_wash = visits >= VISITS_FOR_FREE_WASH

    if visits < VISITS_FOR_GIFT:
        next_reward_name = "Regalo especial"
        visits_left = VISITS_FOR_GIFT - visits
        progress_pct = int((visits / VISITS_FOR_GIFT) * 100)
    elif visits < VISITS_FOR_FREE_WASH:
        next_reward_name = "Lavado gratis"
        visits_left = VISITS_FOR_FREE_WASH - visits
        progress_pct = int(((visits - VISITS_FOR_GIFT) / (VISITS_FOR_FREE_WASH - VISITS_FOR_GIFT)) * 100)
    else:
        next_reward_name = "¡Lavado gratis disponible!"
        visits_left = 0
        progress_pct = 100

    history = [
        {
            "date": item.get("date"),
            "note": item.get("note", "Visita registrada"),
            "by": item.get("by", ""),
        }
        for item in reversed(doc.get("visit_history") or [])  # Más reciente primero
    ]

    return {
        "id": str(doc["_id"]),
        "full_name": doc.get("full_name", ""),
        "first_name": (doc.get("full_name", "") or "").split(" ")[0],
        "username": doc.get("username", ""),
        "birth_date": doc.get("birth_date", ""),
        "birthday_label": birth.strftime("%d/%m") if birth else "",
        "phone": doc.get("phone", ""),
        "role": doc.get("role", "client"),
        "visits": visits,
        "last_visit": doc.get("last_visit"),
        "has_gift": has_gift,
        "has_free_wash": has_free_wash,
        "next_reward_name": next_reward_name,
        "visits_left": visits_left,
        "progress_pct": progress_pct,
        "history": history,
        "is_birthday_month": is_birthday_month(doc.get("birth_date", "")),
        "is_birthday_today": is_birthday_today(doc.get("birth_date", "")),
        "created_at": doc.get("created_at"),
    }


def _serialize_service(doc):
    """Servicio listo para plantillas (sin los bytes de la foto)."""
    updated = doc.get("image_updated_at")
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "category": doc.get("category", ""),
        "icon": doc.get("icon") or "fa-solid fa-car",
        "badge": doc.get("badge", ""),
        "description": doc.get("description", ""),
        "features": list(doc.get("features") or []),
        "image_url": doc.get("image_url", ""),        # Foto externa (opcional)
        "has_image": bool(doc.get("image_type")),      # Foto subida y guardada en MongoDB
        "image_version": int(updated.timestamp()) if isinstance(updated, datetime) else 0,
        "order": doc.get("order", 0),
    }


def _serialize_product(doc):
    """Producto listo para plantillas (sin los bytes de la foto)."""
    if not doc:
        return None
    updated = doc.get("image_updated_at")
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "brand": doc.get("brand", ""),
        "category": doc.get("category", ""),
        "icon": doc.get("icon") or "fa-solid fa-flask",
        "eco": bool(doc.get("eco", False)),
        "description": doc.get("description", ""),
        "benefits": list(doc.get("benefits") or []),
        "image_url": doc.get("image_url", ""),
        "has_image": bool(doc.get("image_type")),
        "image_version": int(updated.timestamp()) if isinstance(updated, datetime) else 0,
        "order": doc.get("order", 0),
    }


# ---------------------------------------------------------------------------
# Inicialización y datos de ejemplo
# ---------------------------------------------------------------------------

def init_db():
    """Crea índices y carga datos iniciales solo si las colecciones están vacías."""
    database = get_db()
    database.users.create_index([("username", ASCENDING)], unique=True)

    if database.users.count_documents({}) == 0:
        _seed_users(database)
    if database.services.count_documents({}) == 0:
        database.services.insert_many([dict(s) for s in SEED_SERVICES])
    if database.products.count_documents({}) == 0:
        database.products.insert_many([dict(p) for p in SEED_PRODUCTS])
    if database.assets.count_documents({"_id": "logo"}) == 0 and os.path.exists(DEFAULT_LOGO_PATH):
        with open(DEFAULT_LOGO_PATH, "rb") as fh:
            save_logo(fh.read(), "image/svg+xml", "nexus-logo.svg")


def _seed_users(database):
    today = datetime.now()
    users = [
        # (nombre, usuario, contraseña, nacimiento, teléfono, rol, visitas)
        ("Administrador NEXUS", "admin", "admin123", "1988-06-15", "+54 9 11 5555-0100", "admin", 0),
        # Cumple HOY y tiene 5 visitas: regalo de cumpleaños activo + premio de 4 visitas desbloqueado
        ("Carlos Mendoza", "carlos92", "cliente123", f"1992-{today.month:02d}-{min(today.day, 28):02d}",
         "+54 9 11 4455-8899", "client", 5),
        ("María González", "mariag", "cliente123", "1995-03-24", "+54 9 11 3322-1100", "client", 2),
        # 9 visitas: desbloqueó regalo de 4 visitas y lavado gratis de 8 visitas
        ("Lucas Valenzuela", "lucas_v8", "cliente123", "1986-11-28", "+54 9 11 9988-7766", "client", 9),
    ]
    docs = []
    for name, username, password, birth, phone, role, visits in users:
        history = []
        if visits > 0:
            history = [
                {"date": _now(), "note": f"Visita #{i + 1} en NEXUS CAR WASH", "by": "sistema"}
                for i in range(visits)
            ]
        docs.append({
            "full_name": name,
            "username": username,
            "password_hash": generate_password_hash(password),
            "birth_date": birth,
            "phone": phone,
            "role": role,
            "visits": visits,
            "last_visit": _now() if visits else None,
            "visit_history": history,
            "created_at": _now(),
        })
    database.users.insert_many(docs)


SEED_SERVICES = [
    {
        "order": 1,
        "name": "Lavado Foam & Gloss",
        "category": "Lavado exterior",
        "icon": "fa-solid fa-soap",
        "badge": "Más elegido",
        "description": "Lavado artesanal con espuma activa pH neutro y secado con microfibra de alta densidad, sin marcas ni micro-rayas.",
        "features": ["Prelavado con cañón de espuma", "Lavado a mano en dos baldes", "Limpieza de llantas y pasaruedas", "Acondicionador de neumáticos"],
        "image_url": "https://images.unsplash.com/photo-1601362840469-51e4d8d58785?auto=format&fit=crop&w=900&q=80",
    },
    {
        "order": 2,
        "name": "Encerado Carnauba Gold",
        "category": "Protección y brillo",
        "icon": "fa-solid fa-wand-magic-sparkles",
        "badge": "Efecto espejo",
        "description": "Cera de carnauba brasileña aplicada a mano que deja un brillo profundo y repele agua y suciedad durante semanas.",
        "features": ["Descontaminado con clay bar", "Carnauba grado 1 aplicada a mano", "Curado con lámpara infrarroja", "Hidrofobia inmediata"],
        "image_url": "https://images.unsplash.com/photo-1520340356584-f9917d1eea6f?auto=format&fit=crop&w=900&q=80",
    },
    {
        "order": 3,
        "name": "Tapicería & Ozono Spa",
        "category": "Interiores",
        "icon": "fa-solid fa-couch",
        "badge": "Renovación total",
        "description": "Inyección y extracción en asientos y alfombras, más desinfección con ozono para eliminar olores y bacterias.",
        "features": ["Aspirado ciclónico profundo", "Inyección-extracción en tapizados", "Nutrición de plásticos y vinilos", "Sanitización con ozono"],
        "image_url": "https://images.unsplash.com/photo-1507136566006-cfc505b114fc?auto=format&fit=crop&w=900&q=80",
    },
    {
        "order": 4,
        "name": "Cerámico Nanotecnológico 9H",
        "category": "Detailing profesional",
        "icon": "fa-solid fa-shield-halved",
        "badge": "Exclusivo",
        "description": "Sellado cerámico de dureza 9H que blinda la pintura contra rayos UV, lluvia ácida y contaminantes por hasta 2 años.",
        "features": ["Corrección de barniz en 2 pasos", "Sellado cerámico bicapa", "Hidrofobia extrema", "Certificado de aplicación"],
        "image_url": "https://images.unsplash.com/photo-1617814076367-b759c7d7e738?auto=format&fit=crop&w=900&q=80",
    },
    {
        "order": 5,
        "name": "Nutrición de Cuero",
        "category": "Interiores",
        "icon": "fa-solid fa-hand-sparkles",
        "badge": "",
        "description": "Limpieza enzimática suave y nutrición con aceites naturales que devuelven flexibilidad y aroma original al cuero.",
        "features": ["Cepillado con cerdas suaves", "Crema de lanolina y ceras naturales", "Filtro UV anti-grietas", "Acabado mate de fábrica"],
        "image_url": "https://images.unsplash.com/photo-1583267746897-2cf415887172?auto=format&fit=crop&w=900&q=80",
    },
    {
        "order": 6,
        "name": "Spa de Motor",
        "category": "Mecánica y detailing",
        "icon": "fa-solid fa-gears",
        "badge": "",
        "description": "Limpieza del vano motor con vapor seco y protectores dieléctricos que cuidan sensores, conexiones y mangueras.",
        "features": ["Desengrase biodegradable", "Vapor seco controlado", "Sellador para plásticos y gomas", "Protección anti-óxido"],
        "image_url": "https://images.unsplash.com/photo-1486006920555-c77dce18193b?auto=format&fit=crop&w=900&q=80",
    },
]

SEED_PRODUCTS = [
    {
        "name": "Ceras de Carnauba Orgánicas",
        "brand": "Swissvax · Meguiar's Pro",
        "category": "Protección de pintura",
        "icon": "fa-solid fa-shield-heart",
        "eco": True,
        "description": "Cera pura de palma brasileña, libre de destilados de petróleo que dañan el barniz.",
        "benefits": ["Biodegradable", "Hidrofobia gota a gota", "Sin residuos blancos"],
    },
    {
        "name": "Siliconas sin solventes",
        "brand": "Gtechniq · CarPro",
        "category": "Interiores y neumáticos",
        "icon": "fa-solid fa-spray-can-sparkles",
        "eco": True,
        "description": "Fórmulas al agua que penetran los polímeros en lugar de dejar una capa grasa que atrae polvo.",
        "benefits": ["Acabado mate original", "Cero pegajosidad", "Filtro UV"],
    },
    {
        "name": "Shampoo pH neutro",
        "brand": "Koch-Chemie",
        "category": "Lavado y descontaminado",
        "icon": "fa-solid fa-droplet",
        "eco": True,
        "description": "Shampoo concentrado con lubricantes que encapsulan la suciedad para que se deslice sin rayar.",
        "benefits": ["pH 7 exacto", "Seguro para cerámicos", "Bajo consumo de agua"],
    },
    {
        "name": "Selladores de cuarzo y grafeno",
        "brand": "Gyeon · Nanolex",
        "category": "Nanotecnología",
        "icon": "fa-solid fa-gem",
        "eco": False,
        "description": "Matriz de SiO2 con grafeno que disipa el calor y evita las marcas de agua por evaporación.",
        "benefits": ["Dureza de laboratorio", "Efecto autolimpiante", "Larga duración"],
    },
]


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

def authenticate(username, password):
    """Devuelve el usuario serializado si las credenciales son correctas."""
    doc = get_db().users.find_one({"username": (username or "").strip().lower()})
    if doc and check_password_hash(doc.get("password_hash", ""), password or ""):
        return _serialize_user(doc)
    return None


def get_user_by_id(user_id):
    oid = _to_object_id(user_id)
    if oid is None:
        return None
    return _serialize_user(get_db().users.find_one({"_id": oid}))


def get_user_by_username(username):
    """Devuelve el usuario serializado por su nombre de usuario."""
    doc = get_db().users.find_one({"username": (username or "").strip().lower()})
    return _serialize_user(doc) if doc else None


def username_exists(username, exclude_id=None):
    query = {"username": (username or "").strip().lower()}
    oid = _to_object_id(exclude_id) if exclude_id else None
    if oid is not None:
        query["_id"] = {"$ne": oid}
    return get_db().users.count_documents(query) > 0


def create_user(full_name, username, password, birth_date, phone="", role="client", visits=0):
    """Crea un usuario y devuelve su id (str). Lanza ValueError si el usuario ya existe."""
    v_count = max(0, int(visits or 0))
    now = _now()
    history = []
    if v_count > 0:
        history.append({"date": now, "note": f"Registro con {v_count} visitas iniciales", "by": "sistema"})

    doc = {
        "full_name": full_name.strip(),
        "username": username.strip().lower(),
        "password_hash": generate_password_hash(password),
        "birth_date": birth_date.strip(),
        "phone": (phone or "").strip(),
        "role": role,
        "visits": v_count,
        "last_visit": now if v_count else None,
        "visit_history": history,
        "created_at": now,
    }
    try:
        result = get_db().users.insert_one(doc)
    except Exception as exc:  # pymongo o mongomock
        if _is_duplicate_error(exc):
            raise ValueError("Ese nombre de usuario ya está en uso.") from exc
        raise
    return str(result.inserted_id)


def update_user(user_id, full_name, username, birth_date, phone="", role="client", password=None, visits=None):
    """Edición total de los datos de un usuario.

    Permite modificar todos los campos personales, corregir las visitas acumuladas,
    y si se ingresa una nueva contraseña la actualiza (útil si el cliente la olvidó).
    """
    oid = _to_object_id(user_id)
    if oid is None:
        return False

    changes = {
        "full_name": full_name.strip(),
        "username": username.strip().lower(),
        "birth_date": birth_date.strip(),
        "phone": (phone or "").strip(),
        "role": role,
        "updated_at": _now(),
    }
    if password:
        changes["password_hash"] = generate_password_hash(password)
    if visits is not None:
        try:
            changes["visits"] = max(0, int(visits))
        except (ValueError, TypeError):
            pass

    try:
        result = get_db().users.update_one({"_id": oid}, {"$set": changes})
    except Exception as exc:
        if _is_duplicate_error(exc):
            raise ValueError("Ese nombre de usuario ya pertenece a otra persona.") from exc
        raise
    return result.matched_count == 1


def add_visit(user_id, note="", by=""):
    """Registra una visita para el cliente (+1 visita) y actualiza su historial."""
    oid = _to_object_id(user_id)
    doc = get_db().users.find_one({"_id": oid}, {"visits": 1}) if oid else None
    if not doc:
        raise ValueError("Cliente no encontrado.")

    now = _now()
    clean_note = (note or "Visita al lavadero").strip()[:200]
    update = {
        "$inc": {"visits": 1},
        "$set": {"last_visit": now},
        "$push": {"visit_history": {
            "date": now,
            "note": clean_note,
            "by": by or "sistema",
        }},
    }
    get_db().users.update_one({"_id": oid}, update)
    current_visits = int(doc.get("visits", 0) or 0) + 1
    return current_visits


def delete_user(user_id):
    oid = _to_object_id(user_id)
    if oid is None:
        return False
    return get_db().users.delete_one({"_id": oid}).deleted_count == 1


def get_all_users():
    """Listado para la tabla del admin (sin contraseña ni historial, para que sea liviano)."""
    docs = get_db().users.find({}, {"password_hash": 0, "visit_history": 0}).sort("created_at", -1)
    return [_serialize_user(doc) for doc in docs]


def get_dashboard_stats():
    clients = [u for u in get_all_users() if u["role"] == "client"]
    return {
        "total_clients": len(clients),
        "total_visits": sum(u["visits"] for u in clients),
        "clients_with_gift": sum(1 for u in clients if u["has_gift"]),
        "clients_with_free_wash": sum(1 for u in clients if u["has_free_wash"]),
        "birthday_today": sum(1 for u in clients if u["is_birthday_today"]),
        "birthday_this_month": sum(1 for u in clients if u["is_birthday_month"]),
    }


# ---------------------------------------------------------------------------
# Catálogo de servicios (las fotos subidas se guardan como binario en MongoDB)
# ---------------------------------------------------------------------------

def get_services():
    docs = get_db().services.find({}, {"image_data": 0}).sort("order", 1)
    return [_serialize_service(doc) for doc in docs]


def get_service(service_id):
    oid = _to_object_id(service_id)
    if oid is None:
        return None
    doc = get_db().services.find_one({"_id": oid}, {"image_data": 0})
    return _serialize_service(doc) if doc else None


def create_service(data):
    """Crea un servicio. `data`: name, category, description, features, badge, icon, image_url."""
    last = list(get_db().services.find({}, {"order": 1}).sort("order", -1).limit(1))
    order = (last[0].get("order", 0) if last else 0) + 1
    result = get_db().services.insert_one({**data, "order": order, "created_at": _now()})
    return str(result.inserted_id)


def update_service(service_id, data):
    oid = _to_object_id(service_id)
    if oid is None:
        return False
    result = get_db().services.update_one({"_id": oid}, {"$set": {**data, "updated_at": _now()}})
    return result.matched_count == 1


def delete_service(service_id):
    oid = _to_object_id(service_id)
    if oid is None:
        return False
    return get_db().services.delete_one({"_id": oid}).deleted_count == 1


def save_service_image(service_id, data, content_type):
    oid = _to_object_id(service_id)
    if oid is None:
        return False
    get_db().services.update_one({"_id": oid}, {"$set": {
        "image_data": Binary(data),
        "image_type": content_type,
        "image_updated_at": _now(),
    }})
    return True


def remove_service_image(service_id):
    oid = _to_object_id(service_id)
    if oid is not None:
        get_db().services.update_one({"_id": oid}, {"$unset": {"image_data": "", "image_type": "", "image_updated_at": ""}})


def get_service_image(service_id):
    oid = _to_object_id(service_id)
    if oid is None:
        return None
    doc = get_db().services.find_one({"_id": oid}, {"image_data": 1, "image_type": 1})
    if not doc or not doc.get("image_data"):
        return None
    return {"data": bytes(doc["image_data"]), "content_type": doc.get("image_type", "image/jpeg")}


# ---------------------------------------------------------------------------
# Catálogo de productos utilizados (insumos con fotos en MongoDB)
# ---------------------------------------------------------------------------

def get_products():
    """Devuelve todos los productos serializados listos para plantillas."""
    docs = get_db().products.find({}, {"image_data": 0}).sort("order", 1)
    return [_serialize_product(doc) for doc in docs]


def get_product(product_id):
    oid = _to_object_id(product_id)
    if oid is None:
        return None
    doc = get_db().products.find_one({"_id": oid}, {"image_data": 0})
    return _serialize_product(doc) if doc else None


def create_product(data):
    """Crea un producto. `data`: name, brand, category, description, benefits, eco, icon, image_url."""
    last = list(get_db().products.find({}, {"order": 1}).sort("order", -1).limit(1))
    order = (last[0].get("order", 0) if last else 0) + 1
    result = get_db().products.insert_one({**data, "order": order, "created_at": _now()})
    return str(result.inserted_id)


def update_product(product_id, data):
    oid = _to_object_id(product_id)
    if oid is None:
        return False
    result = get_db().products.update_one({"_id": oid}, {"$set": {**data, "updated_at": _now()}})
    return result.matched_count == 1


def delete_product(product_id):
    oid = _to_object_id(product_id)
    if oid is None:
        return False
    return get_db().products.delete_one({"_id": oid}).deleted_count == 1


def save_product_image(product_id, data, content_type):
    oid = _to_object_id(product_id)
    if oid is None:
        return False
    get_db().products.update_one({"_id": oid}, {"$set": {
        "image_data": Binary(data),
        "image_type": content_type,
        "image_updated_at": _now(),
    }})
    return True


def remove_product_image(product_id):
    oid = _to_object_id(product_id)
    if oid is not None:
        get_db().products.update_one({"_id": oid}, {"$unset": {"image_data": "", "image_type": "", "image_updated_at": ""}})


def get_product_image(product_id):
    oid = _to_object_id(product_id)
    if oid is None:
        return None
    doc = get_db().products.find_one({"_id": oid}, {"image_data": 1, "image_type": 1})
    if not doc or not doc.get("image_data"):
        return None
    return {"data": bytes(doc["image_data"]), "content_type": doc.get("image_type", "image/jpeg")}


# ---------------------------------------------------------------------------
# Logotipo (almacenado como binario en la colección "assets")
# ---------------------------------------------------------------------------

def save_logo(data, content_type, filename):
    get_db().assets.update_one(
        {"_id": "logo"},
        {"$set": {
            "data": Binary(data),
            "content_type": content_type,
            "filename": filename,
            "size": len(data),
            "updated_at": _now(),
        }},
        upsert=True,
    )


def get_logo():
    """Devuelve el logo completo (con bytes) o None."""
    doc = get_db().assets.find_one({"_id": "logo"})
    if not doc or not doc.get("data"):
        return None
    return {
        "data": bytes(doc["data"]),
        "content_type": doc.get("content_type", "image/png"),
        "filename": doc.get("filename", "logo"),
    }


def get_logo_meta():
    """Devuelve solo los metadatos del logo (sin bytes) para las plantillas."""
    doc = get_db().assets.find_one({"_id": "logo"}, {"data": 0})
    if not doc:
        return None
    updated = doc.get("updated_at")
    version = int(updated.timestamp()) if isinstance(updated, datetime) else 0
    return {"filename": doc.get("filename", ""), "version": version, "updated_at": updated}
