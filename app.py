from flask import Flask, render_template, request, redirect, session
import json
from datetime import datetime
import os
import requests
import base64

app = Flask(__name__)
app.secret_key = 'clave-secreta'
IMG_API_KEY = '46f80f415dea98ec668e1e581fe8b825'  # Tu API de imgbb

# === SUBIDA DE DATOS ===
@app.route('/subir_datos', methods=['GET', 'POST'])
def subir_datos():
    if 'usuario' not in session or session.get('rol') != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        tipo = request.form.get('tipo')

        if tipo == 'nuevo':
            json_file = request.files.get('json_file')
            image = request.files.get('image')

            if not json_file or not image:
                return render_template("mensaje.html", mensaje="❌ Debes subir un archivo JSON y una imagen.")

            try:
                image_data = base64.b64encode(image.read()).decode('utf-8')
                res = requests.post("https://api.imgbb.com/1/upload", data={
                    "key": IMG_API_KEY,
                    "image": image_data
                })

                if res.status_code != 200:
                    return render_template("mensaje.html", mensaje="❌ Error al subir imagen a imgbb.")

                image_url = res.json()['data']['url']
                nuevo = json.load(json_file)

                resp = requests.post("https://juntas-vecinales.onrender.com/agregar_dato", json={
                    "persona": nuevo,
                    "imagen_url": image_url
                })

                if resp.status_code == 200:
                    return render_template("mensaje.html", mensaje="✅ Datos enviados correctamente.")
                return f"❌ Error del servidor externo: {resp.text}"

            except Exception as e:
                return render_template("mensaje.html", mensaje=f"❌ Error: {str(e)}")

        elif tipo == 'eliminar':
            dni = request.form.get('dni')
            if not dni:
                return "❌ Debes ingresar un DNI válido."

            try:
                resp = requests.post("https://juntas-vecinales.onrender.com/eliminar_dato", json={"dni": dni})
                if resp.status_code == 200:
                    return render_template("mensaje.html", mensaje="✅ Datos eliminados correctamente.")
                return render_template("mensaje.html", mensaje=f"❌ Error del servidor externo: {resp.text}")
            except Exception as e:
                return f"❌ Error de conexión: {str(e)}"

    return render_template("subir_datos.html")

# === FUNCIONES AUXILIARES ===
def cargar_json(nombre):
    if os.path.exists(nombre):
        with open(nombre, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("solicitudes", [])
            except json.JSONDecodeError:
                return []
    return []

def guardar_json(nombre, data):
    with open(nombre, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generar_id_unico(lista):
    if not lista:
        return 0
    ids = [item.get("id", i) for i, item in enumerate(lista)]
    return max(ids) + 1

# === INICIO Y LOGIN ===
@app.route('/')
def inicio():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    return render_template('login.html')

@app.route('/ingresar', methods=['POST'])
def ingresar():
    usuario = request.form['usuario']
    clave = request.form['clave']
    usuarios = cargar_json('usuariospermitidos.json')

    for u in usuarios:
        if u.get('usuario') == usuario and u.get('clave') == clave:
            session['usuario'] = usuario
            session['rol'] = u.get('rol')
            return redirect('/panel')

    return redirect('/login?error=1')

# === PANEL ===
@app.route('/panel')
def panel():
    if 'usuario' not in session:
        return redirect('/login')
    return render_template('panel.html', usuario=session['usuario'], rol=session.get('rol'), anio=datetime.now().year)

# === AGREGAR MIEMBRO ===
@app.route('/agregar')
def agregar():
    if 'usuario' not in session:
        return redirect('/login')
    return render_template('agregar.html')

@app.route('/solicitud/agregar', methods=['POST'])
def solicitud_agregar():
    if 'usuario' not in session:
        return redirect('/')

    campos = [
        "region_policial", "division_policial", "departamento", "provincia", "distrito",
        "comisaria", "tipo", "nombre_jjvv", "resolucion", "fecha", "zona", "apellidos",
        "nombres", "edad", "sexo", "dni", "nacionalidad", "ocupacion", "direccion",
        "cargo", "telefono"
    ]

    datos = {campo: request.form.get(campo, "") for campo in campos}
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')

    solicitudes = cargar_json('solicitudes.json')
    solicitud = {
        "id": generar_id_unico(solicitudes),
        "tipo": "agregar",
        "usuario": session['usuario'],
        "datos": datos,
        "fecha_solicitud": ahora,
        "estado": "pendiente"
    }

    solicitudes.append(solicitud)
    guardar_json('solicitudes.json', solicitudes)

    registro = {
        "usuario": session['usuario'],
        "accion": "agregar",
        "datos": datos,
        "fecha": ahora,
        "estado": "pendiente"
    }

    registros = cargar_json('registros.json')
    registros.append(registro)
    guardar_json('registros.json', registros)

    return render_template('enviado.html')

# === ELIMINAR MIEMBRO ===
@app.route('/eliminar')
def eliminar():
    if 'usuario' not in session:
        return redirect('/login')
    return render_template('eliminar.html')

@app.route('/solicitud/eliminar', methods=['POST'])
def eliminar_miembro():
    if 'usuario' not in session:
        return redirect('/')

    dni = request.form["dni"]
    fecha = request.form["fecha"]
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")

    solicitudes = cargar_json("solicitudes.json")
    datos = {"dni": dni, "fecha": fecha, "tipo_solicitud": "eliminacion"}

    solicitud = {
        "id": generar_id_unico(solicitudes),
        "tipo": "eliminar",
        "usuario": session["usuario"],
        "fecha_solicitud": ahora,
        "datos": datos,
        "estado": "pendiente"
    }

    solicitudes.append(solicitud)
    guardar_json("solicitudes.json", solicitudes)

    registro = {
        "usuario": session["usuario"],
        "accion": "eliminar",
        "datos": datos,
        "fecha": ahora,
        "estado": "pendiente"
    }

    registros = cargar_json("registros.json")
    registros.append(registro)
    guardar_json("registros.json", registros)

    return render_template("enviado.html")

# === VER REGISTROS ===
@app.route('/registros')
def registros():
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    todos = cargar_json('registros.json')
    registros_usuario = [r for r in todos if r['usuario'] == usuario]

    return render_template('registros.html', usuario=usuario, registros=registros_usuario)

@app.route('/eliminar_registro', methods=['POST'])
def eliminar_registro():
    if 'usuario' not in session:
        return redirect('/')

    id_registro = int(request.form['id'])
    usuario = session['usuario']
    registros = cargar_json('registros.json')
    registros_usuario = [r for r in registros if r['usuario'] == usuario]

    if 0 <= id_registro < len(registros_usuario):
        registros.remove(registros_usuario[id_registro])
        guardar_json('registros.json', registros)

    return redirect('/registros')

# === ADMIN: GESTIÓN DE SOLICITUDES ===
@app.route('/solicitudes')
def ver_solicitudes():
    if session.get('rol') != 'admin':
        return redirect('/panel')

    solicitudes = cargar_json('solicitudes.json')
    solicitudes = [s for s in solicitudes if isinstance(s, dict) and 'datos' in s]
    return render_template('solicitudes.html', solicitudes=solicitudes)

@app.route('/aprobar', methods=['POST'])
def aprobar():
    try:
        solicitud_id = int(request.form['solicitud_id'])
        solicitudes = cargar_json("solicitudes.json")

        for solicitud in solicitudes:
            if solicitud.get("id") == solicitud_id:
                solicitud['estado'] = "aceptado"

                registros = cargar_json("registros.json")
                for r in registros:
                    if (r.get('usuario') == solicitud.get('usuario') and
                        r.get('datos') == solicitud.get('datos') and
                        r.get('accion') == solicitud.get('tipo')):
                        r['estado'] = 'aceptado'
                guardar_json("registros.json", registros)
                break

        guardar_json("solicitudes.json", solicitudes)

    except Exception as e:
        print(f"[ERROR al aprobar]: {e}")

    return redirect('/solicitudes')

@app.route('/rechazar', methods=['POST'])
def rechazar():
    try:
        solicitud_id = int(request.form['solicitud_id'])
        solicitudes = cargar_json("solicitudes.json")

        for solicitud in solicitudes:
            if solicitud.get("id") == solicitud_id:
                solicitud['estado'] = "rechazado"

                registros = cargar_json("registros.json")
                for r in registros:
                    if (r.get('usuario') == solicitud.get('usuario') and
                        r.get('datos') == solicitud.get('datos') and
                        r.get('accion') == solicitud.get('tipo')):
                        r['estado'] = 'rechazado'
                guardar_json("registros.json", registros)
                break

        guardar_json("solicitudes.json", solicitudes)

    except Exception as e:
        print(f"[ERROR al rechazar]: {e}")

    return redirect('/solicitudes')

# === CERRAR SESIÓN ===
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# === INICIO DEL SERVIDOR ===
if __name__ == '__main__':
    app.run(debug=True)
