import os
import pathlib
import requests
from flask import Flask, render_template, request, abort, redirect, url_for, session, flash
import time
from flask_mysqldb import MySQL, MySQLdb
import conexion as db
from werkzeug.security import check_password_hash
from datetime import datetime
from datetime import date
from tkinter import *
from tkinter import messagebox as MessageBox
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
# Ruta para imagenes
UPLOAD_FOLDER = '/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Configurar la aplicacion para ser ejecutado
template_dir = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
template_dir = os.path.join(template_dir, 'src', 'templates')
# Declaramos la variable de ejecución de la aplicación
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'llave_secreta'
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = "438918858309-hd4i8644fg5gok7cqultaa1uppd3fkp8.apps.googleusercontent.com"
client_secrets_file = os.path.join(
    pathlib.Path(__file__).parent, "client_secret.json")

# config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '54321'
app.config['MYSQL_DB'] = 'Buzon'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
conexion = MySQL(app)

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)

# Ruta principal
@app.route('/')
def home():
    return render_template('home.html')


def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Authorization required
        else:
            return function()

    return wrapper


@app.route("/glogin")
def glogin():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(
        session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    # Obtener el correo electrónico del usuario (si se solicita)
    if "email" in id_info:
        session["email"] = id_info["email"]

     # Guardar la información del usuario en la base de datos MySQL
    cursor = db.conexion.cursor()
    user_data = (session["google_id"], session["name"], session["email"])
    insert_query = "INSERT INTO googleauth (google_id, nombre, email) VALUES (%s, %s, %s)"
    cursor.execute(insert_query, user_data)
    db.conexion.commit()
    cursor.close()

    flash("Inicio de sesión exitoso", "success")
    
    return redirect("/protected_area")


@app.route("/protected_area")
@login_is_required
def protected_area():
    # Obtén el nombre del usuario desde la sesión
    name = session.get("name", "Usuario Desconocido")
    email = session.get("email")

    # Puedes pasar name como una variable a tu plantilla HTML
    return render_template("protected_area.html", name=name, email=email)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'email' in request.form and 'contrasena' in request.form:
        email = str(request.form['email'])
        contrasena = str(request.form['contrasena'])
        # Verificar credenciales
        cursor = conexion.connection.cursor()
        cursor.execute(
            'SELECT * from usuario WHERE Correo = %s AND Contrasena = %s', (email, contrasena,))
        account = cursor.fetchone()

        if account is not None:
            # Si las credenciales son válidas, se establece la sesión del usuario
            session['Ingresado'] = True
            session['idUsuario'] = account['idUsuario']
            session['Correo'] = email[1]

            return redirect(url_for('Buzon'))
        else:
            # Si las credenciales son inválidas, se redirige al formulario de inicio de sesión nuevamente
            return render_template('login.html', message="Credenciales inválidas")

    # Si es una solicitud GET, mostrar el formulario de inicio de sesion
    return render_template('login.html')


@app.route('/Buzon')
def Buzon():
    return render_template('Buzon.html')


@app.route('/perfil')
def perfil():
    return render_template('perfil.html')


@app.route('/contrasena')
def contrasena():
    return render_template('settings.html')

# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    # Eliminar la información de sesión del usuario
    session.clear()
    return redirect(url_for('login'))


@app.route('/contacto')
def contacto():
    return render_template('contacto.html')


@app.route('/guardar_queja_sugerencia', methods=['POST'])
def guardar_queja_sugerencia():
    if 'idUsuario' in session:
        idUsuario = session['idUsuario']
    tipo = request.form['tipo']
    mensaje = request.form['mensaje']
    sugerencia = request.form['sugerencia']
    current_date = datetime.now().strftime(
        "%Y-%m-%dT%H:%M")  # Obtener fecha y hora actual
    cursor = conexion.connection.cursor()
    try:
        with conexion.connection.cursor() as cursor:
            cursor.execute('INSERT INTO Queja (Id_Usuario, Tipo, FechaRegistro, Mensaje, Sugerencia) VALUES (%s, %s, %s, %s, %s)',
                           (idUsuario, tipo, current_date, mensaje, sugerencia))
            conexion.connection.commit()
    finally:
        conexion.connection.close()
    return redirect(url_for('Buzon', current_date=current_date))


@app.route('/user', methods=['GET'])
def user():
    cursor = db.conexion.cursor()
    cursor.execute("SELECT * FROM Usuario")
    datosDB_usuario = cursor.fetchall()
    # Convertir los datos a diccionario para la tabla Usuario
    insertObjeto_usuario = []
    columnName_usuario = [column[0] for column in cursor.description]
    for registro in datosDB_usuario:
        insertObjeto_usuario.append(dict(zip(columnName_usuario, registro)))

    cursor2 = db.conexion.cursor()
    cursor2.execute("SELECT * FROM Queja")
    datosDB_otraTabla = cursor2.fetchall()
    # Convertir los datos a diccionario para la otra tabla
    insertObjeto_otraTabla = []
    columnName_otraTabla = [column[0] for column in cursor2.description]
    for registro in datosDB_otraTabla:
        insertObjeto_otraTabla.append(
            dict(zip(columnName_otraTabla, registro)))

    cursor.close()
    cursor2.close()
    return render_template('indexUsuario.html', data_user=insertObjeto_usuario, data_queja=insertObjeto_otraTabla)

# Ruta para ingresar usuarios
@app.route('/insertUsuario', methods=['POST'])
def insertUsuario():
    # Importamos las variables desde el form del indexUsuario.html
    id = request.form["usuarioid"]
    correo = request.form["usuariocorreo"]
    contra = request.form["usuariocontra"]

    if correo and contra:
        cursor = db.conexion.cursor()
        sql = """INSERT INTO Usuario (idUsuario, Correo, Contrasena)
            VALUES (%s, %s, %s) """
        # Declaramos a "datos" como una variable tipo tupla para mandar información
        datos = (id, correo, contra)
        cursor.execute(sql, datos)
        db.conexion.commit()
    return redirect(url_for('login'))

# Ruta para modificar usuario
@app.route('/actualizaUsuario/<string:id>', methods=['POST'])
def actualizaUsuario(id):
    # Importamos las variables desde el form del indexUsuario.html
    correo = request.form["usuariocorreo"]
    contra = request.form["usuariocontra"]

    if correo and contra:
        cursor = db.conexion.cursor()
        sql = """UPDATE Usuario
            SET Correo= %s,
                Contrasena = %s
            WHERE IdUsuario =%s"""
        # Declaramos a "datos" como una variable tipo tupla para mandar la información
        datos = (correo, contra, id)
        cursor.execute(sql, datos)
        db.conexion.commit()
    return redirect(url_for('user'))

# Ruta para eliminar registros
@app.route('/eliminaUsuario/<string:idUsuario>')
def eliminaUsuario(idUsuario):
    resultado = MessageBox.askokcancel(
        "Eliminar...", "¿Estas seguro de eliminar el registro?")
    if resultado == TRUE:
        cursor = db.conexion.cursor()
        sql = """DELETE FROM Usuario
                    WHERE idUsuario=%s"""
        # Declaramos a "datos" como una variable tipo tupla para mandar la información
        datos = (idUsuario,)
        cursor.execute(sql, datos)
        db.conexion.commit()
    return redirect(url_for('user'))

# Eliminar queja
@app.route('/deleteQueja/<string:id>')
def deleteQueja(id):
    resultado = MessageBox.askokcancel(
        "Eliminar...", "¿Estas seguro de eliminar el registro?")
    if resultado == TRUE:
        cursor = db.conexion.cursor()
        sql = """DELETE FROM Queja
                    WHERE idQueja=%s"""
        # Declaramos a "datos" como una variable tipo tupla para mandar la información
        datos = (id,)
        cursor.execute(sql, datos)
        db.conexion.commit()
    return redirect(url_for('user'))

# Ruta para modificar queja
@app.route('/actualizaQueja/<string:id>', methods=['POST'])
def actualizaQueja(id):
    # Importamos las variables desde el form del indexUsuario.html
    quejaestatus = request.form["quejaestatus"]
    fechafin = datetime.now().strftime(
        "%Y-%m-%dT%H:%M")  # Obtener fecha y hora actual
    cursor = db.conexion.cursor()

    if quejaestatus and fechafin:
        sql = """UPDATE Queja
            SET Estatus= %s,
                FechaFin = %s
            WHERE idQueja =%s"""
        # Declaramos a "datos" como una variable tipo tupla para mandar la información
        datos = (quejaestatus, fechafin, id)
        cursor.execute(sql, datos)
        db.conexion.commit()
    return redirect(url_for('user'))


@app.route('/Estatus', methods=['GET'])
def Estatus():
    idUsuario = session['idUsuario']
    cursor = db.conexion.cursor()
    # Recuperar las quejas del usuario
    cursor.execute("SELECT * FROM Queja WHERE Id_Usuario = %s", [idUsuario])
    quejas = cursor.fetchall()

    insertObject = []
    columnNames = [column[0] for column in cursor.description]
    for record in quejas:
        insertObject.append(dict(zip(columnNames, record)))
    cursor.close()
    return render_template('perfil.html', data_estatus=quejas)


@app.route('/cambiarContrasena',  methods=['GET', 'POST'])
def cambiarContrasena():
    if 'idUsuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['Nuevacontra']

        cursor = conexion.connection.cursor()
        query = "UPDATE Usuario SET Contrasena = %s WHERE idUsuario = %s"
        cursor.execute(query, (new_password, session['idUsuario']))
        conexion.connection.commit()

    return redirect(url_for('contrasena', message="Contraseña cambiada."))


# Definimos el __name__ como plantilla principal a index.html y el puerto de ejecución
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
