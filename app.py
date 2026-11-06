from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import sqlite3
import csv
import io
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = "harry_barber_secret_2026_super_seguro!"
ADMIN_PASSWORD = "HarryAdmin2026!" 

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS citas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  fecha TEXT, hora TEXT, cliente TEXT, telefono TEXT, 
                  servicio TEXT, direccion TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bloqueos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  fecha TEXT, hora_inicio TEXT, hora_fin TEXT, dia_completo INTEGER)''')
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logueado'):
            return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS DE LA WEB PÚBLICA ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/citas-ocupadas', methods=['GET'])
def citas_ocupadas():
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    
    # Citas normales
    c.execute("SELECT fecha, hora FROM citas WHERE estado != 'cancelada'")
    citas = [{"fecha": row[0], "hora": row[1]} for row in c.fetchall()]
    
    # Bloqueos
    c.execute("SELECT fecha, hora_inicio, hora_fin, dia_completo FROM bloqueos")
    bloqueos_raw = c.fetchall()
    conn.close()
    
    horas_estandar = ['09:00','10:00','11:00','12:00','16:00','17:00','18:00','19:00']
    bloqueos_procesados = []
    
    for b in bloqueos_raw:
        fecha, h_inicio, h_fin, dia_completo = b
        if dia_completo == 1:
            for h in horas_estandar:
                bloqueos_procesados.append({"fecha": fecha, "hora": h})
        else:
            for h in horas_estandar:
                if h_inicio <= h < h_fin:
                    bloqueos_procesados.append({"fecha": fecha, "hora": h})

    return jsonify(citas + bloqueos_procesados)

@app.route('/api/reservar', methods=['POST'])
def reservar():
    datos = request.json
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    
    # COMPROBACIÓN EN EL SERVIDOR: Si la hora ya está ocupada, rechazamos
    c.execute("SELECT id FROM citas WHERE fecha = ? AND hora = ? AND estado != 'cancelada'", 
              (datos['fecha'], datos['hora']))
    if c.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Esta hora acaba de ser reservada por otra persona."}), 400

    c.execute("INSERT INTO citas (fecha, hora, cliente, telefono, servicio, direccion, estado) VALUES (?, ?, ?, ?, ?, ?, 'pendiente')",
              (datos['fecha'], datos['hora'], datos['nombre'], datos['telefono'], datos['servicio'], datos['direccion']))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# --- DASHBOARD (ZONA PRIVADA) ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logueado'] = True
            return redirect(url_for('admin'))
        return "Contraseña incorrecta"
    
    if not session.get('logueado'):
        return '''
        <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Login - Harry Barber</title>
        <style>body{background:#090909;color:#d7ad60;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
        form{background:#141310;padding:40px;border-radius:20px;border:1px solid #d7ad60;text-align:center;}
        input{padding:15px;font-size:1.2rem;border-radius:10px;border:1px solid #d7ad60;background:#000;color:#fff;margin-top:20px;width:100%;box-sizing:border-box;}
        button{background:#d7ad60;color:#000;border:none;padding:15px 30px;font-size:1.2rem;font-weight:bold;border-radius:10px;margin-top:20px;width:100%;cursor:pointer;}</style>
        </head><body><form method="POST"><h2>Acceso Administrador</h2>
        <input type="password" name="password" placeholder="Contraseña" required>
        <button type="submit">Entrar</button></form></body></html>'''

    hoy = datetime.now().date()
    en_tres_dias = hoy + timedelta(days=3)

    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    c.execute("SELECT * FROM citas ORDER BY fecha DESC, hora ASC")
    todas_citas = c.fetchall()
    
    fecha_limite_str = en_tres_dias.strftime('%Y-%m-%d')
    c.execute("""SELECT * FROM citas WHERE fecha >= ? AND fecha <= ? AND estado != 'cancelada' ORDER BY fecha ASC, hora ASC""", (hoy.strftime('%Y-%m-%d'), fecha_limite_str))
    proximas_citas = c.fetchall()
    
    c.execute("SELECT * FROM bloqueos ORDER BY fecha DESC")
    bloqueos = c.fetchall()
    conn.close()
    
    html = '''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Panel - Harry Barber</title>
        <style>
            body { background-color: #090909; color: #f8f5ef; font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .header img { max-width: 220px; border-radius: 15px; border: 2px solid #d7ad60; }
            h1 { color: #d7ad60; margin-top: 15px; font-size: 2rem; }
            .nav-links { display: flex; justify-content: center; gap: 20px; margin-bottom: 30px; }
            .nav-links a { color: #d7ad60; text-decoration: none; font-size: 1.1rem; border: 1px solid #d7ad60; padding: 10px 20px; border-radius: 8px; }
            .nav-links a:hover { background-color: #d7ad60; color: #000; }
            
            .urgentes-title { color: #ef4444; font-size: 1.6rem; margin-bottom: 15px; margin-top: 40px; border-bottom: 2px solid #ef4444; padding-bottom: 10px; }
            .cita-urgente { background-color: #141310; border-left: 5px solid #ef4444; padding: 20px; border-radius: 10px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;}
            .cita-urgente .info { font-size: 1.2rem; }
            .cita-urgente .info b { color: #d7ad60; }
            .cita-urgente .botones { display: flex; gap: 10px; }
            
            .tabla-title { color: #d7ad60; font-size: 1.6rem; margin-bottom: 15px; margin-top: 40px; border-bottom: 2px solid #d7ad60; padding-bottom: 10px;}
            .table-container { overflow-x: auto; }
            table { width: 100%; border-collapse: collapse; background-color: #141310; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 30px; min-width: 800px; }
            th { background-color: #d7ad60; color: #000; padding: 15px; text-align: left; font-size: 1.1rem; }
            td { padding: 15px; border-bottom: 1px solid #333; font-size: 1.1rem; }
            tr:hover { background-color: #1a1916; }
            
            .btn { padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin: 2px; font-size: 1rem; text-align:center;}
            .btn-confirm { background-color: #10b981; color: white; }
            .btn-cancel { background-color: #ef4444; color: white; }
            .btn-delete { background-color: #555; color: white; }
            .btn:hover { opacity: 0.8; }
            
            .add-form { background-color: #141310; padding: 25px; border-radius: 15px; margin-top: 40px; border: 1px solid #d7ad60; }
            .add-form h3 { color: #d7ad60; margin-top: 0; font-size: 1.5rem; }
            .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
            .form-grid input, .form-grid select { padding: 15px; border-radius: 8px; border: 1px solid #555; background-color: #000; color: #fff; font-size: 1.1rem; width: 100%; box-sizing: border-box; }
            .btn-add { background-color: #d7ad60; color: #000; padding: 15px; border: none; border-radius: 8px; font-size: 1.2rem; font-weight: bold; cursor: pointer; width: 100%; margin-top: 15px; grid-column: 1 / -1; }
            .btn-add:hover { background-color: #f4d89a; }
            
            @media (max-width: 768px) {
                .form-grid { grid-template-columns: 1fr; }
                th, td { font-size: 0.9rem; padding: 10px; }
                .cita-urgente { flex-direction: column; align-items: flex-start; }
                .header img { max-width: 180px; }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <img src="/static/logo.jpg" alt="Logo Harry Barber" onerror="this.style.display='none'">
            <h1>Panel de Gestión</h1>
        </div>
        
        <div class="nav-links">
            <a href="/admin/exportar">📥 Descargar Excel (CSV)</a>
            <a href="/logout">🚪 Salir</a>
        </div>
    '''

    # SECCIÓN URGENTE
    html += '<div class="urgentes-title">🔥 Citas Próximas (Hoy, mañana y pasado)</div>'
    if len(proximas_citas) == 0:
        html += '<p style="color:#aaa; font-size:1.2rem;">No tienes citas para los próximos 3 días.</p>'
    else:
        for c in proximas_citas:
            try:
                fecha_obj = datetime.strptime(c[1], '%Y-%m-%d')
                fecha_bonita = fecha_obj.strftime('%A, %d de %B').capitalize()
            except:
                fecha_bonita = c[1]
                
            html += f'''
            <div class="cita-urgente">
                <div class="info">
                    <b>{fecha_bonita}</b> a las <b>{c[2]}</b><br>
                    👤 {c[3]} | 📞 {c[4]}<br>
                    ✂️ {c[5]} | 📍 {c[6]}
                </div>
                <div class="botones">
            '''
            if c[7] == 'pendiente':
                html += f"<a class='btn btn-confirm' href='/admin/estado/{c[0]}/confirmada'>Confirmar</a>"
            html += f"<a class='btn btn-cancel' href='/admin/estado/{c[0]}/cancelada'>Cancelar</a>"
            html += f"<a class='btn btn-delete' href='/admin/borrar/{c[0]}' onclick=\"return confirm('¿Borrar cita?');\">🗑️</a>"
            html += '</div></div>'

    # HISTORIAL
    html += '<div class="tabla-title">📋 Historial Completo de Citas</div>'
    if len(todas_citas) == 0:
        html += '<p style="color:#aaa; font-size:1.2rem;">Aún no hay ninguna cita registrada.</p>'
    else:
        html += '<div class="table-container"><table><tr><th>Fecha</th><th>Hora</th><th>Cliente</th><th>Teléfono</th><th>Servicio</th><th>Dirección</th><th>Estado</th><th>Acciones</th></tr>'
        for c in todas_citas:
            color_estado = "#10b981" if c[7] == 'confirmada' else ("#ef4444" if c[7] == 'cancelada' else "#f59e0b")
            html += f"<tr><td><b>{c[1]}</b></td><td><b>{c[2]}</b></td><td>{c[3]}</td><td>{c[4]}</td><td>{c[5]}</td><td>{c[6]}</td>"
            html += f"<td style='color:{color_estado}; font-weight:bold;'>{c[7].upper()}</td><td>"
            if c[7] == 'pendiente':
                html += f"<a class='btn btn-confirm' href='/admin/estado/{c[0]}/confirmada'>Confirmar</a>"
            if c[7] != 'cancelada':
                html += f"<a class='btn btn-cancel' href='/admin/estado/{c[0]}/cancelada'>Cancelar</a>"
            html += f"<a class='btn btn-delete' href='/admin/borrar/{c[0]}' onclick=\"return confirm('¿Borrar cita?');\">🗑️</a></td></tr>"
        html += '</table></div>'

    # --- SECCIÓN BLOQUEO MEJORADA ---
    html += '''
    <div class="add-form" style="border-color: #ef4444; background-color: #1a0f0f;">
        <h3 style="color: #ef4444;">🚫 Gestión de Bloqueos (Vacaciones / Descanso)</h3>
        <form action="/admin/bloquear" method="POST">
            <div class="form-grid">
                <div style="grid-column: 1 / -1;">
                    <label style="color:#ef4444; font-weight:bold; margin-bottom:5px; display:block;">Tipo de bloqueo:</label>
                    <select name="tipo_bloqueo" id="tipoBloqueo" style="width:100%; padding:15px; border-radius:8px; background:#000; color:#fff; border:1px solid #ef4444;">
                        <option value="dia_completo">Día Completo (Todo el día libre)</option>
                        <option value="rango_horas">Rango de Horas (Ej: solo por la tarde)</option>
                    </select>
                </div>
                <div style="grid-column: 1 / -1;">
                    <input type="date" name="fecha" required>
                </div>
                <div id="rangoHorasDiv" style="display:none; grid-column: 1 / -1; grid-template-columns: 1fr 1fr; gap:15px;">
                    <div>
                        <label style="color:#fff; font-size:0.9rem;">Desde:</label>
                        <select name="hora_inicio" style="width:100%; padding:15px; border-radius:8px; background:#000; color:#fff; border:1px solid #555;">
                            <option value="09:00">09:00</option><option value="10:00">10:00</option><option value="11:00">11:00</option><option value="12:00">12:00</option>
                            <option value="16:00">16:00</option><option value="17:00">17:00</option><option value="18:00">18:00</option>
                        </select>
                    </div>
                    <div>
                        <label style="color:#fff; font-size:0.9rem;">Hasta (sin incluir):</label>
                        <select name="hora_fin" style="width:100%; padding:15px; border-radius:8px; background:#000; color:#fff; border:1px solid #555;">
                            <option value="10:00">10:00</option><option value="11:00">11:00</option><option value="12:00">12:00</option><option value="13:00">13:00</option>
                            <option value="17:00">17:00</option><option value="18:00">18:00</option><option value="19:00">19:00</option><option value="20:00">20:00</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn-add" style="background-color:#ef4444; color:white; grid-column: 1 / -1;">Aplicar Bloqueo</button>
            </div>
        </form>
        <script>
            document.getElementById('tipoBloqueo').addEventListener('change', function() {
                document.getElementById('rangoHorasDiv').style.display = this.value === 'rango_horas' ? 'grid' : 'none';
            });
        </script>
    </div>
    '''
    
    if len(bloqueos) > 0:
        html += '<div class="tabla-title" style="color:#ef4444; font-size:1.2rem; margin-top:30px;">Bloqueos Activos</div>'
        html += '<div class="table-container"><table><tr><th>Fecha</th><th>Tipo</th><th>Horario</th><th>Acción</th></tr>'
        for b in bloqueos:
            tipo = "Día Completo" if b[4] == 1 else "Rango de horas"
            horario = "Todo el día" if b[4] == 1 else f"{b[2]} a {b[3]}"
            html += f"<tr><td>{b[1]}</td><td>{tipo}</td><td>{horario}</td><td><a class='btn btn-confirm' href='/admin/desbloquear/{b[0]}'>Desbloquear</a></td></tr>"
        html += '</table></div>'

    # FORMULARIO MANUAL
    html += '''
        <div class="add-form">
            <h3>Añadir cita manual</h3>
            <form action="/admin/anadir" method="POST">
                <div class="form-grid">
                    <input type="date" name="fecha" required>
                    <input type="time" name="hora" required>
                    <input type="text" name="cliente" placeholder="Nombre" required>
                    <input type="text" name="telefono" placeholder="Teléfono">
                    <input type="text" name="servicio" placeholder="Servicio (ej: Corte)">
                    <input type="text" name="direccion" placeholder="Dirección">
                    <button type="submit" class="btn-add">Añadir Cita</button>
                </div>
            </form>
        </div>
    </body>
    </html>
    '''
    return html

# --- RUTAS DE ACCIÓN ---
@app.route('/admin/estado/<int:id>/<string:nuevo_estado>')
@login_required
def cambiar_estado(id, nuevo_estado):
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    c.execute("UPDATE citas SET estado = ? WHERE id = ?", (nuevo_estado, id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/borrar/<int:id>')
@login_required
def borrar_cita(id):
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    c.execute("DELETE FROM citas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/anadir', methods=['POST'])
@login_required
def añadir_manual():
    fecha = request.form.get('fecha')
    hora = request.form.get('hora')
    cliente = request.form.get('cliente')
    telefono = request.form.get('telefono')
    servicio = request.form.get('servicio')
    direccion = request.form.get('direccion')
    
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    c.execute("INSERT INTO citas (fecha, hora, cliente, telefono, servicio, direccion, estado) VALUES (?, ?, ?, ?, ?, ?, 'confirmada')", (fecha, hora, cliente, telefono, servicio, direccion))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# --- RUTAS DE BLOQUEO ---
@app.route('/admin/bloquear', methods=['POST'])
@login_required
def bloquear_hora():
    fecha = request.form.get('fecha')
    tipo = request.form.get('tipo_bloqueo')
    
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    
    if tipo == 'dia_completo':
        c.execute("INSERT INTO bloqueos (fecha, hora_inicio, hora_fin, dia_completo) VALUES (?, '00:00', '23:59', 1)", (fecha,))
    else:
        h_inicio = request.form.get('hora_inicio')
        h_fin = request.form.get('hora_fin')
        c.execute("INSERT INTO bloqueos (fecha, hora_inicio, hora_fin, dia_completo) VALUES (?, ?, ?, 0)", (fecha, h_inicio, h_fin))
        
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/desbloquear/<int:id>')
@login_required
def desbloquear_hora(id):
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    c.execute("DELETE FROM bloqueos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# --- EXPORTAR CSV ---
@app.route('/admin/exportar')
@login_required
def exportar_csv():
    conn = sqlite3.connect('citas.db')
    c = conn.cursor()
    c.execute("SELECT fecha, hora, cliente, telefono, servicio, direccion, estado FROM citas ORDER BY fecha, hora")
    citas = c.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Fecha', 'Hora', 'Cliente', 'Telefono', 'Servicio', 'Direccion', 'Estado'])
    writer.writerows(citas)
    
    csv_bytes = b'\xef\xbb\xbf' + output.getvalue().encode('utf-8')
    return send_file(io.BytesIO(csv_bytes), mimetype='text/csv', as_attachment=True, download_name='citas_harry_barber.csv')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)