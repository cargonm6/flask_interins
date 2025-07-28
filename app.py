import os
import re
import sqlite3

import numpy as np
import plotly.graph_objects as go
import unicodedata
from cryptography.fernet import Fernet
from flask import Flask, render_template, request, jsonify, g
from plotly.subplots import make_subplots

app = Flask(__name__, instance_relative_config=True)
app.config['SESSION_COOKIE_NAME'] = None
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecret')

# === Rutas ===
INSTANCE_DB_PATH = os.path.join(app.instance_path, "database.db")
ENC_DB_PATH = os.path.join("instance", "database.db.enc")
DEC_DB_PATH = INSTANCE_DB_PATH

# === Crear carpetas necesarias ===
os.makedirs(app.instance_path, exist_ok=True)


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
    # Construir consulta base
    query = '''
        SELECT persona.nombre, persona.apellidos, grupo.especialidad
        FROM persona
        JOIN posicion ON persona.id = posicion.persona_id
        JOIN grupo ON grupo.id = posicion.grupo_id
        WHERE 1 = 1
    '''
    params = []

    if nombre:
        query += ' AND UPPER(persona.nombre) LIKE ?'
        params.append(f'%{remove_accents(nombre).upper()}%')
    if apellidos:
        query += ' AND UPPER(persona.apellidos) LIKE ?'
        params.append(f'%{remove_accents(apellidos).upper()}%')
    if especialidad:
        query += ' AND UPPER(grupo.especialidad) LIKE ?'
        params.append(f'%{remove_accents(especialidad).upper()}%')

    query += ' GROUP BY persona.nombre, persona.apellidos, grupo.especialidad'

    results = cur.execute(query, params).fetchall()

    # Devolver como lista de dicts
    return [
        {'NOMBRE': n, 'APELLIDOS': a, 'ESPECIALIDAD': e}
        for n, a, e in results
    ] if results else None


def graficar_persona(esp, ape, nom):
    cur = get_db().cursor()

    # Igual que antes...
    query_persona = '''
        SELECT posicion.anyo, posicion.numero, grupo.especialidad, persona.nombre, persona.apellidos
        FROM persona
        JOIN posicion ON persona.id = posicion.persona_id
        JOIN grupo ON grupo.id = posicion.grupo_id
        WHERE UPPER(grupo.especialidad) = ?
        ORDER BY posicion.anyo
    '''
    rows = cur.execute(query_persona, (esp.upper(),)).fetchall()

    nom_norm = remove_accents(nom).upper()
    ape_norm = remove_accents(ape).upper()
    # esp_norm = remove_accents(esp).upper()

    persona_data = [(a, n) for a, n, e, nombre, apellidos in rows
                    if nom_norm in remove_accents(nombre).upper()
                    and ape_norm in remove_accents(apellidos).upper()]

    if not persona_data:
        return None

    persona_dict = {a: n for a, n in persona_data}

    query_total = '''
        SELECT posicion.anyo, COUNT(*)
        FROM posicion
        JOIN grupo ON grupo.id = posicion.grupo_id
        WHERE upper(grupo.especialidad) = ?
        GROUP BY posicion.anyo
    '''
    totales = dict(cur.execute(query_total, (esp.upper(),)).fetchall())

    years = list(range(2004, 2026))
    numeros = [persona_dict.get(y, None) for y in years]
    totales_lista = [totales.get(y, 0) for y in years]

    # Porcentaje inverso
    pct_inverso = [round((1 - (n / t)) * 100, 1) if n and t else None for n, t in zip(numeros, totales_lista)]

    # Crear figura Plotly con subplots
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        subplot_titles=[f"Posición en bolsa",
                                        f"Tamaño de bolsa y posición anual"])

    # === Línea de evolución (arriba) ===
    fig.add_trace(go.Scatter(x=years, y=numeros, mode='lines+markers',
                             name="Posición",
                             hoverinfo='x+y',
                             line=dict(color='#840032')), row=1, col=1)

    # Anotaciones de % en gráfico superior
    # Alternar anotaciones arriba y abajo para evitar solapamiento
    shift_values = [15, -15]  # arriba, abajo
    shift_index = 0  # índice para alternar

    for x, y, pct in zip(years, numeros, pct_inverso):
        if y is not None and not np.isnan(y):
            yshift = shift_values[shift_index % 2]
            fig.add_annotation(x=x, y=y, text=f"{pct:.1f}%", showarrow=False, yshift=yshift, row=1, col=1,
                               font=dict(size=10, color='#02040f'))
            shift_index += 1

    # Añadir barras primero
    fig.add_trace(go.Bar(x=years, y=totales_lista, name="Tamaño bolsa", marker_color='#e5dada'), row=2, col=1)

    # max_total = max(totales_lista)

    for x, y_pos in zip(years, numeros):
        total = totales_lista[x - years[0]]

        # Línea roja, si hay posición
        if y_pos is not None:
            fig.add_trace(go.Scatter(
                x=[x - 0.3, x + 0.3],
                y=[y_pos, y_pos],
                mode='lines',
                line=dict(color='#840032', width=2),
                showlegend=False
            ), row=2, col=1)

            fig.add_annotation(
                x=x,
                y=y_pos,
                yshift=15,
                text=str(int(y_pos)),
                showarrow=False,
                font=dict(size=10, color='#840032'),
                row=2, col=1
            )
        if total > 0:
            # Texto azul sobre barra
            fig.add_annotation(
                x=x,
                y=total,
                yshift=15,
                text=str(total),
                showarrow=False,
                font=dict(size=10, color='#005089'),
                row=2, col=1
            )

    # Formato general
    fig.update_yaxes(autorange="reversed", title_text="Posición", row=1, col=1)
    fig.update_yaxes(title_text="Total", row=2, col=1)
    fig.update_xaxes(tickmode="array", tickvals=years, tickangle=90, title_text="Años", row=1, col=1,
                     showticklabels=True)
    fig.update_xaxes(tickmode="array", tickvals=years, tickangle=90, title_text="Años", row=2, col=1)
    fig.update_layout(
        title_text=f"{nom} {ape} - {esp}",
        title_x=0.5,
        title_font=dict(size=18),
        showlegend=False,
        margin=dict(t=60, b=40),
        autosize=True,
    )

    return fig.to_html(full_html=False, include_plotlyjs='cdn', config={"responsive": True})


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
    graph_html = None

    if request.method == "POST":
        busqueda = request.form.get("busqueda")
        if busqueda:
            partes = [p.strip() for p in busqueda.split(",")]
            if len(partes) == 3:
                ape, nom, esp = partes
                coincidencias = buscar_coincidencias(especialidad=esp, apellidos=ape, nombre=nom)
                if coincidencias:
                    persona = coincidencias[0]
                    graph_html = graficar_persona(
                        persona['ESPECIALIDAD'],
                        persona['APELLIDOS'],
                        persona['NOMBRE']
                    )
                    if graph_html:
                        return render_template("index.html", graph_html=graph_html, error=None)
                    else:
                        error = "No se pudo generar la gráfica."
                else:
                    error = "No se encontraron coincidencias."
            else:
                error = "Formato de búsqueda incorrecto. Usa: Apellidos, Nombre, Especialidad"
        else:
            error = "Debes introducir un valor."
        return render_template("index.html", graph_html=None, error=error)

    return render_template("index.html", graph_html=graph_html, error=None)


@app.route("/autocomplete")
def autocomplete():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    parts = [p.strip() for p in query.split(",")]
    while len(parts) < 3:
        parts.append("")
    apellido_q, nombre_q, especialidad_q = map(remove_accents, parts)

    # Convertir a mayúsculas para que el filtro sea case-insensitive
    apellido_q = apellido_q.upper()
    nombre_q = nombre_q.upper()
    especialidad_q = especialidad_q.upper()

    sql = '''
        SELECT DISTINCT persona.apellidos, persona.nombre, grupo.especialidad
        FROM persona
        JOIN posicion ON persona.id = posicion.persona_id
        JOIN grupo ON grupo.id = posicion.grupo_id
        WHERE UPPER(persona.apellidos) LIKE ?
          AND UPPER(persona.nombre) LIKE ?
          AND UPPER(grupo.especialidad) LIKE ?
        LIMIT 10
    '''
    params = (
        f'%{apellido_q}%' if apellido_q else '%',
        f'%{nombre_q}%' if nombre_q else '%',
        f'%{especialidad_q}%' if especialidad_q else '%'
    )

    cur = get_db().cursor()
    results = cur.execute(sql, params).fetchall()

    combinados = [f"{apellidos}, {nombre}, {especialidad}" for apellidos, nombre, especialidad in results]

    return jsonify(combinados)


if __name__ == "__main__":
    app.run(debug=True)
