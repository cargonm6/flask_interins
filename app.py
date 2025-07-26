import os
import re
import sqlite3

import matplotlib
import unicodedata

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from flask import Flask, render_template, request, jsonify, g
from cryptography.fernet import Fernet

app = Flask(__name__, instance_relative_config=True)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecret')

# === Rutas ===
INSTANCE_DB_PATH = os.path.join(app.instance_path, "database.db")
IMG_FOLDER = os.path.join("static", "img")
ENC_DB_PATH = os.path.join("instance", "database.db.enc")
DEC_DB_PATH = INSTANCE_DB_PATH

# === Crear carpetas necesarias ===
os.makedirs(app.instance_path, exist_ok=True)
os.makedirs(IMG_FOLDER, exist_ok=True)


# === Función para descifrar la base de datos ===
def descifrar_db_si_necesario():
    if not os.path.exists(DEC_DB_PATH) and os.path.exists(ENC_DB_PATH):
        key = os.environ.get("DB_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("La variable DB_ENCRYPTION_KEY no está definida.")

        fernet = Fernet(key.encode())
        with open(ENC_DB_PATH, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = fernet.decrypt(encrypted_data)

        with open(DEC_DB_PATH, "wb") as f:
            f.write(decrypted_data)

        print("🔓 Base de datos desencriptada correctamente.")


# === Descifrar la base si es necesario ===
descifrar_db_si_necesario()

# === Asegurarse de que la base existe ===
if not os.path.exists(INSTANCE_DB_PATH):
    conn = sqlite3.connect(INSTANCE_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS persona (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# === Ruta de la base de datos para Flask ===
DB_FILE = INSTANCE_DB_PATH


def remove_accents(text):
    if not isinstance(text, str):
        return text
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if not unicodedata.combining(c))


def buscar_coincidencias(especialidad=None, apellidos=None, nombre=None):
    cur = get_db().cursor()
    # Traemos todo, sin filtro SQL
    query = '''
        SELECT persona.nombre, persona.apellidos, grupo.especialidad
        FROM persona
        JOIN posicion ON persona.id = posicion.persona_id
        JOIN grupo ON grupo.id = posicion.grupo_id
        GROUP BY persona.nombre, persona.apellidos, grupo.especialidad
    '''
    results = cur.execute(query).fetchall()

    # Normalizamos el input
    nom_norm = remove_accents(nombre or "").lower()
    ape_norm = remove_accents(apellidos or "").lower()
    esp_norm = remove_accents(especialidad or "").lower()

    for n, a, e in results:
        n_norm = remove_accents(n).lower()
        a_norm = remove_accents(a).lower()
        e_norm = remove_accents(e).lower()
        if ((not nombre or nom_norm in n_norm)
                and (not apellidos or ape_norm in a_norm)
                and (not especialidad or esp_norm in e_norm)):
            return {'NOMBRE': n, 'APELLIDOS': a, 'ESPECIALIDAD': e}
    return None


def graficar_persona(esp, ape, nom):
    cur = get_db().cursor()

    query_persona = '''
        SELECT posicion.anyo, posicion.numero, grupo.especialidad, persona.nombre, persona.apellidos
        FROM persona
        JOIN posicion ON persona.id = posicion.persona_id
        JOIN grupo ON grupo.id = posicion.grupo_id
        WHERE lower(grupo.especialidad) = ?
        ORDER BY posicion.anyo
    '''
    rows = cur.execute(query_persona, (esp.lower(),)).fetchall()

    nom_norm = remove_accents(nom).lower()
    ape_norm = remove_accents(ape).lower()
    esp_norm = remove_accents(esp).lower()

    persona_data = []
    for anyo, numero, especialidad, nombre, apellidos in rows:
        if (nom_norm in remove_accents(nombre).lower()
                and ape_norm in remove_accents(apellidos).lower()
                and esp_norm in remove_accents(especialidad).lower()):
            persona_data.append((anyo, numero))

    if not persona_data:
        return None

    # Diccionario año -> número de la persona
    persona_dict = {anyo: numero for anyo, numero in persona_data}

    query_total = '''
        SELECT posicion.anyo, COUNT(*)
        FROM posicion
        JOIN grupo ON grupo.id = posicion.grupo_id
        WHERE lower(grupo.especialidad) = ?
        GROUP BY posicion.anyo
    '''
    totales = dict(cur.execute(query_total, (esp.lower(),)).fetchall())

    years = list(range(2004, 2026))

    numeros = [persona_dict.get(anyo, np.nan) for anyo in years]
    totales_lista = [totales.get(anyo, 0) for anyo in years]

    fig = plt.figure(figsize=(16, 9))
    grid = plt.GridSpec(2, 1)

    # === Gráfico superior ===
    ax1 = fig.add_subplot(grid[0, 0])
    ax1.plot(years, numeros, marker='o', linestyle='-')
    ax1.set_title(f"Evolución de la posición en bolsa ({esp}) de {nom} {ape}")
    ax1.set_xlabel("Año")
    ax1.set_ylabel("Posición en bolsa")
    ax1.set_xticks(years)
    ax1.invert_yaxis()
    ax1.grid(True)
    ax1.set_xlim(2003, 2026)

    min_val = min([x for x in numeros if str(x) != "nan"])
    max_val = max([x for x in numeros if str(x) != "nan"])
    rango = max_val - min_val
    margen = rango * 0.1  # 10% del rango
    ax1.set_ylim(top=min_val - margen, bottom=max_val + margen)

    pct_inverso = []
    for num, tot in zip(numeros, totales_lista):
        if np.isnan(num) or tot == 0:
            pct_inverso.append(0)
        else:
            pct_inverso.append(1 - (num / tot))

    for x, y, pct, tot in zip(years, numeros, pct_inverso, totales_lista):
        if not np.isnan(y):
            ax1.annotate(f"{pct * 100:.1f}%", (x, y),
                         textcoords="offset points", xytext=(0, 10), ha='center',
                         fontsize=9, color='green')

    # === Gráfico inferior ===
    ax2 = fig.add_subplot(grid[1, 0])
    ax2.bar(years, totales_lista, color='lightgray')

    for x, total, y in zip(years, totales_lista, numeros):
        # Texto encima de cada barra: total de especialidad
        if total != 0:
            ax2.text(x, total + 1, str(total), ha='center', va='bottom',
                     fontsize=9, color='blue')
        if not np.isnan(y):
            # Línea roja indicando la posición de la persona
            ax2.hlines(y=y, xmin=x - 0.4, xmax=x + 0.4, colors='red', linewidth=2)
            # Texto encima de la línea roja: posición personal
            ax2.text(x, y + 1, str(int(y)), ha='center', va='bottom',
                     fontsize=9, color='red')

    ax2.set_title(f"Tamaño de la bolsa ({esp}) y posición de {nom} {ape}")
    ax2.set_xlabel("Año")
    ax2.set_ylabel("Número de personas en bolsa")
    ax2.set_xticks(years)
    ax2.grid(axis='y')
    ax2.set_xlim(2003, 2026)
    ax2.set_ylim(top=int(max(totales_lista) * 1.1))

    plt.tight_layout()

    filename = sanitize_filename(f"{esp}_{ape}_{nom}.png")
    filepath = os.path.join(IMG_FOLDER, filename)
    plt.savefig(filepath)
    plt.close()

    return filename


def sanitize_filename(filename):
    # Normaliza y elimina acentos
    nfkd_form = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    # Reemplaza espacios por guiones bajos
    only_ascii = only_ascii.replace(' ', '_')
    # Elimina cualquier carácter que no sea letra, número, guion bajo, guion o punto
    only_ascii = re.sub(r'[^A-Za-z0-9._-]', '', only_ascii)
    return only_ascii


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_FILE)
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.route("/", methods=["GET", "POST"])
def index():
    error = None
    image_path = None

    if request.method == "POST":
        busqueda = request.form.get("busqueda")
        if busqueda:
            partes = [p.strip() for p in busqueda.split(",")]
            if len(partes) == 3:
                ape, nom, esp = partes
                persona = buscar_coincidencias(especialidad=esp, apellidos=ape, nombre=nom)
                if persona:
                    filename = graficar_persona(persona['ESPECIALIDAD'], persona['APELLIDOS'], persona['NOMBRE'])
                    if filename:
                        image_path = f"/{IMG_FOLDER}/{filename}"
                    else:
                        error = "No se pudo generar la gráfica."
                else:
                    error = "No se encontraron coincidencias."
            else:
                error = "Formato de búsqueda incorrecto. Usa: Apellido, Nombre, Especialidad"
        else:
            error = "Debes introducir un valor."

    return render_template("index.html", image_path=image_path, error=error)


@app.route("/autocomplete")
def autocomplete():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])

    parts = [p.strip() for p in query.split(",")]
    while len(parts) < 3:
        parts.append("")
    apellido_q, nombre_q, especialidad_q = map(remove_accents, parts)

    sql = '''
        SELECT DISTINCT persona.apellidos, persona.nombre, grupo.especialidad
        FROM persona
        JOIN posicion ON persona.id = posicion.persona_id
        JOIN grupo ON grupo.id = posicion.grupo_id
    '''
    cur = get_db().cursor()
    results = cur.execute(sql).fetchall()

    combinados = []
    for apellidos, nombre, especialidad in results:
        apellidos_norm = remove_accents(apellidos).lower()
        nombre_norm = remove_accents(nombre).lower()
        especialidad_norm = remove_accents(especialidad).lower()

        if apellido_q and apellido_q not in apellidos_norm:
            continue
        if nombre_q and nombre_q not in nombre_norm:
            continue
        if especialidad_q and especialidad_q not in especialidad_norm:
            continue

        combinados.append(f"{apellidos}, {nombre}, {especialidad}")
        if len(combinados) >= 10:
            break

    return jsonify(combinados)


if __name__ == "__main__":
    app.run(debug=True)
