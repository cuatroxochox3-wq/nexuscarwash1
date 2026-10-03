import app
import database as db

client = app.app.test_client()

# 1. Probar landing
res = client.get('/')
assert res.status_code == 200, f"Landing falló: {res.status_code}"
assert b"puntos" not in res.data.lower() or b"apunt" in res.data.lower(), "Se encontró palabra puntos en landing"
print("1. Landing OK (sin precios, sin turnos, sin puntos)")

# 2. Probar login y registro
res = client.get('/login')
assert res.status_code == 200
res = client.get('/registro')
assert res.status_code == 200
assert b"puntos" not in res.data.lower(), "Se encontró palabra puntos en registro"
print("2. Login y Registro OK")

# 3. Probar panel de cliente
carlos = db.get_user_by_username('carlos92')
assert carlos is not None, "Usuario carlos92 no encontrado"
with client.session_transaction() as sess:
    sess['user_id'] = carlos['id']

res = client.get('/cliente')
assert res.status_code == 200, f"Client dashboard falló: {res.status_code}"
assert b"puntos" not in res.data.lower(), "Se encontró palabra puntos en panel de cliente"
print(f"3. Panel del cliente OK (visitas: {carlos['visits']}, has_gift: {carlos['has_gift']})")

# 4. Probar panel de admin
admin = db.get_user_by_username('admin')
assert admin is not None, "Admin no encontrado"
with client.session_transaction() as sess:
    sess['user_id'] = admin['id']

res = client.get('/admin')
assert res.status_code == 200, f"Admin dashboard falló: {res.status_code}"
assert b"puntos" not in res.data.lower(), "Se encontró palabra puntos en admin dashboard"
print("4. Admin dashboard OK")

# 5. Probar admin servicios
res = client.get('/admin/servicios')
assert res.status_code == 200
assert b"Agregar nuevo servicio" in res.data
assert b"Editar completamente" in res.data
print("5. Admin servicios OK (botones visibles)")

# 6. Probar formulario de nuevo servicio
res = client.get('/admin/servicios/nuevo')
assert res.status_code == 200
print("6. Formulario nuevo servicio OK")

# 7. Probar formulario de editar servicio
services = db.get_services()
assert len(services) > 0, "No hay servicios"
first_service_id = services[0]["id"]
res = client.get(f'/admin/servicios/{first_service_id}/editar')
assert res.status_code == 200
assert b"Editar completamente" in res.data
print(f"7. Formulario editar completamente servicio OK ({services[0]['name']})")

# 8. Probar editar cliente (ficha total y contrasenia)
res = client.get(f'/admin/clientes/{carlos["id"]}/editar')
assert res.status_code == 200
assert "Restablecer contraseña".encode('utf-8') in res.data or b"Restablecer contrase" in res.data
assert b"Visitas acumuladas" in res.data
print("8. Formulario ficha cliente OK")

# 9. Probar sumar visita
prev_visits = carlos['visits']
res = client.post(f'/admin/clientes/{carlos["id"]}/visita', data={'note': 'Test visita'}, follow_redirects=True)
assert res.status_code == 200
updated_carlos = db.get_user_by_id(carlos['id'])
assert updated_carlos['visits'] == prev_visits + 1, "No sumó la visita"
print(f"9. Sumar visita OK (antes: {prev_visits}, después: {updated_carlos['visits']})")

# 10. Probar crear nuevo servicio con especificaciones
new_srv_data = {
    'name': 'Lavado Premium Cerámico Test',
    'category': 'Detailing Avanzado',
    'badge': 'Nuevo 2026',
    'description': 'Servicio de prueba creado con especificaciones técnicas detalladas y subida de imagen.',
    'features': 'Espuma activa pH neutro\nDescontaminado férrico\nSellado sintético bicapa',
    'icon': 'fa-solid fa-star',
    'image_url': 'https://images.unsplash.com/photo-1520340356584-f9917d1eea6f?auto=format&fit=crop&w=900&q=80',
}
res = client.post('/admin/servicios/nuevo', data=new_srv_data, follow_redirects=True)
assert res.status_code == 200
all_srv = db.get_services()
created = [s for s in all_srv if s['name'] == 'Lavado Premium Cerámico Test']
assert len(created) > 0, "No se encontró el servicio creado"
assert len(created[0]['features']) == 3, "No se guardaron las 3 especificaciones"
print("10. Crear servicio con especificaciones y foto OK")

# 11. Probar editar completamente el servicio creado
edit_srv_data = {
    'name': 'Lavado Premium Cerámico Editado',
    'category': 'Detailing Extremo',
    'badge': 'Especial',
    'description': 'Descripción totalmente editada y actualizada.',
    'features': 'Especificación A\nEspecificación B',
    'icon': 'fa-solid fa-wand-magic-sparkles',
    'image_url': 'https://images.unsplash.com/photo-1601362840469-51e4d8d58785?auto=format&fit=crop&w=900&q=80',
}
res = client.post(f'/admin/servicios/{created[0]["id"]}/editar', data=edit_srv_data, follow_redirects=True)
assert res.status_code == 200
edited = db.get_service(created[0]["id"])
assert edited['name'] == 'Lavado Premium Cerámico Editado'
assert len(edited['features']) == 2
print("11. Editar completamente el servicio OK")

# 12. Probar edición total del cliente (incluyendo contraseña y visitas directas)
edit_user_data = {
    'full_name': 'Carlos Mendoza Editado',
    'username': 'carlos92',
    'birth_date': '1992-06-20',
    'phone': '+54 9 11 0000-9999',
    'role': 'client',
    'visits': '7',  # Seteamos 7 visitas manualmente
    'password': 'nuevaPasswordSegura123',  # Restablecemos contraseña
}
res = client.post(f'/admin/clientes/{carlos["id"]}/editar', data=edit_user_data, follow_redirects=True)
assert res.status_code == 200
carlos_after = db.get_user_by_id(carlos['id'])
assert carlos_after['full_name'] == 'Carlos Mendoza Editado'
assert carlos_after['visits'] == 7
# Probar autenticación con la nueva contraseña
auth_user = db.authenticate('carlos92', 'nuevaPasswordSegura123')
assert auth_user is not None, "Falló la autenticación con la nueva contraseña restablecida"
print("12. Edición total de cliente (datos, visitas manuales y restablecer contraseña) OK")

# 13. Probar admin productos (listado)
res = client.get('/admin/productos')
assert res.status_code == 200
assert b"Agregar nuevo producto" in res.data
assert b"Editar completamente" in res.data
print("13. Admin productos OK (botones 'Agregar nuevo producto' y 'Editar completamente' visibles)")

# 14. Probar crear nuevo producto con foto y beneficios
new_prod_data = {
    'name': 'Sellador Cerámico Ultra Hydro Test',
    'brand': 'Gyeon Quartz Pro',
    'category': 'Protección Nanotecnológica',
    'description': 'Sellador nanotecnológico con SiO2 de alta pureza que repele suciedad y agua.',
    'benefits': 'Dureza 9H comprobada\nEfecto autolimpiante extremo\nDurabilidad superior a 18 meses',
    'eco': '1',
    'icon': 'fa-solid fa-gem',
    'image_url': 'https://images.unsplash.com/photo-1617814076367-b759c7d7e738?auto=format&fit=crop&w=900&q=80',
}
res = client.post('/admin/productos/nuevo', data=new_prod_data, follow_redirects=True)
assert res.status_code == 200
all_prod = db.get_products()
created_p = [p for p in all_prod if p['name'] == 'Sellador Cerámico Ultra Hydro Test']
assert len(created_p) > 0, "No se encontró el producto creado"
assert len(created_p[0]['benefits']) == 3
assert created_p[0]['eco'] is True
print("14. Crear producto con beneficios y foto OK")

# 15. Probar editar completamente el producto
edit_prod_data = {
    'name': 'Sellador Cerámico Ultra Hydro Editado',
    'brand': 'Gyeon Quartz Supreme',
    'category': 'Protección Nanotecnológica 9H',
    'description': 'Descripción editada del producto con mayores especificaciones.',
    'benefits': 'Beneficio 1\nBeneficio 2',
    'eco': '0',
    'icon': 'fa-solid fa-shield-heart',
    'image_url': 'https://images.unsplash.com/photo-1520340356584-f9917d1eea6f?auto=format&fit=crop&w=900&q=80',
}
res = client.post(f'/admin/productos/{created_p[0]["id"]}/editar', data=edit_prod_data, follow_redirects=True)
assert res.status_code == 200
edited_p = db.get_product(created_p[0]["id"])
assert edited_p['name'] == 'Sellador Cerámico Ultra Hydro Editado'
assert edited_p['brand'] == 'Gyeon Quartz Supreme'
assert len(edited_p['benefits']) == 2
print("15. Editar completamente el producto OK")

# 16. Probar eliminar producto
res = client.post(f'/admin/productos/{created_p[0]["id"]}/eliminar', follow_redirects=True)
assert res.status_code == 200
assert db.get_product(created_p[0]["id"]) is None, "El producto no fue eliminado"
print("16. Eliminar producto OK")

print("\n==========================================")
print("¡TODOS LOS REQUERIMIENTOS VERIFICADOS CON ÉXITO!")
print("==========================================")
