"""
Punto de entrada de NEXUS CAR WASH.
Verifica dependencias, conecta con MongoDB y levanta el servidor web.

    python main.py   ->  http://127.0.0.1:5000
"""

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def check_and_install_dependencies():
    """Instala las dependencias de requirements.txt si falta alguna."""
    try:
        import flask  # noqa: F401
        import pymongo  # noqa: F401
    except ImportError:
        print("[!] Faltan dependencias. Instalando desde requirements.txt...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                                   os.path.join(BASE_DIR, "requirements.txt")])
        except Exception as exc:
            print(f"[X] No se pudo instalar automáticamente: {exc}")
            print("    Ejecuta manualmente: pip install -r requirements.txt")
            sys.exit(1)


if __name__ == "__main__":
    check_and_install_dependencies()
    from app import app

    print("=" * 62)
    print("   NEXUS CAR WASH - Sistema de gestión y fidelización")
    print("=" * 62)
    print("   Abre en tu navegador:  http://127.0.0.1:5000")
    print("   Admin:    admin    / admin123")
    print("   Cliente:  carlos92 / cliente123")
    print("=" * 62)
    app.run(debug=True, host="127.0.0.1", port=5000)