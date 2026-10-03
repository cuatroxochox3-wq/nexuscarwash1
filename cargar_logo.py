"""
Carga el logotipo oficial de NEXUS CAR WASH en MongoDB.

Uso:
    python cargar_logo.py ruta/al/logo.png

Formatos admitidos: PNG, JPG/JPEG, WEBP y SVG (máximo 2 MB).
También se puede subir desde el Panel de administración.
"""

import mimetypes
import os
import sys

import database as db

ALLOWED = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
MAX_BYTES = 2 * 1024 * 1024


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.isfile(path):
        sys.exit(f"[X] No se encontró el archivo: {path}")

    content_type = mimetypes.guess_type(path)[0] or ""
    if path.lower().endswith(".svg"):
        content_type = "image/svg+xml"
    if content_type not in ALLOWED:
        sys.exit("[X] Formato no permitido. Usa PNG, JPG, WEBP o SVG.")

    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) > MAX_BYTES:
        sys.exit("[X] El archivo supera los 2 MB.")

    db.get_db()
    if db.USING_MOCK:
        sys.exit("[X] MongoDB no está disponible: inicia el servicio antes de cargar el logo.")

    db.save_logo(data, content_type, os.path.basename(path))
    print(f"[OK] Logo '{os.path.basename(path)}' guardado en MongoDB ({len(data)} bytes).")


if __name__ == "__main__":
    main()
