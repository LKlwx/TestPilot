from flask import request, g
from datetime import datetime
from extensions import db

def register_middleware(app):
    @app.before_request
    def before_request():
        g.start_time = datetime.now()
        g.ip = request.remote_addr

    @app.after_request
    def after_request(response):
        try:
            db.session.remove()
        except:
            pass
        return response
