import os.path

from flask import Flask, render_template, request, redirect, jsonify
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit

from main import *
import grandlyon

app = Flask(__name__)
bootstrap = Bootstrap()
bootstrap.init_app(app)
socketio = SocketIO(app)

app.config["IMAGE_UPLOADS"] = "/tmp"
app.config["CACHE_DIR"] = os.environ.get("CACHE_DIR", default="")


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
        if request.files:
            data_file = request.files["pdf"]
            if data_file.filename == "":
                app.logger.error('Aucun fichier envoyé')
                return jsonify({'message': 'Aucun fichier envoyé'}), 500

            file_no_ext, file_extension = data_file.filename.rsplit('.', 1)
            filename = secure_filename("{}.{}.{}".format(
                file_no_ext, request.sid, file_extension))

            data_filename = os.path.join(app.config["IMAGE_UPLOADS"], filename)
            data_file.save(data_filename)
            emit('display_message',
                 {'data': "Fichier téléversé, traitement en cours"},
                 namespace='/test')

            cache_file = os.path.join(app.config["CACHE_DIR"],
                                      GEOCODE_CACHE_FILE)
            geocode_cache = pull_cache(cache_file)
            data = None
            try:
                file_extension = data_filename.rsplit('.', 1)[1]
                if file_extension == "pdf":
                    data = prepare_data_from_pdf(data_filename)
                elif file_extension == "html":
                    data = grandlyon.prepare_data_from_html(data_filename)

                data = enrich_data(data, geocode_cache)

            except Exception as error:
                import traceback
                app.logger.error(traceback.format_exc())
                return jsonify({'message': repr(error)}), 500
            emit('display_message',
                 {'data': "Traitement terminé. La carte arrive"},
                 namespace='/test')
            save_cache(geocode_cache, cache_file)

            return create_map(data)._repr_html_()
    app.logger.error('Aucun fichier envoyé')
    return jsonify({'message': 'Aucun fichier envoyé'}), 500
