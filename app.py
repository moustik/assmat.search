import os.path

from flask import Flask, render_template, request, redirect
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit

from main import *

app = Flask(__name__)
bootstrap = Bootstrap()
bootstrap.init_app(app)
socketio = SocketIO(app)

app.config["IMAGE_UPLOADS"] = "/tmp"


@socketio.on('client_connected', namespace='/test')
def handle_client_connect_event(json):
    print('received json: {0}'.format(str(json)))


@app.route("/", methods=["GET"])
def upload():
    return render_template("upload.html")


@app.route("/view", methods=["GET", "POST"])
def view_data():
    request.sid = request.form.get("sid", None)
    if request.method == "POST":
        print(request.files)
        if request.files:
            pdf_file = request.files["pdf"]
            if pdf_file.filename == "":
                print("No filename")
                return redirect(request.url)
            filename = secure_filename("{}.{}.pdf".format(
                pdf_file.filename[:-4], request.sid))

            pdf_filename = os.path.join(app.config["IMAGE_UPLOADS"], filename)
            pdf_file.save(pdf_filename)
            emit('display_message',
                 {'data': "Fichier téléversé, traitement en cours"},
                 namespace='/test')

            geocode_cache = pull_cache()
            data = prepare_data_from_pdf(pdf_filename, cache=geocode_cache)
            emit('display_message',
                 {'data': "Traitement terminé. La carte arrive"},
                 namespace='/test')
            save_cache(geocode_cache)

            return create_map(data)._repr_html_()
    return None
