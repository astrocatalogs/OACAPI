"""API for the Open Astronomy Catalogs."""
import json
import os

from flask import Flask
from flask_restful import Api, Resource

# Create a engine for connecting to SQLite3.
# Assuming salaries.db is in your app root folder

app = Flask(__name__)
api = Api(app)


class Catalog(Resource):
    """Return whole catalog."""

    global catalog

    def get(self):
        """Get result."""
        return catalog


class Event(Resource):
    """Return single event."""

    global catalog

    def get(self, event_name):
        """Get result."""
        return catalog.get(event_name, {})


api.add_resource(Event, '/event/<string:event_name>')
api.add_resource(Catalog, '/catalog')

if __name__ == '__main__':
    global catalog
    json.loads(os.path.join(
        '/root', 'astrocats', 'astrocats', 'tidaldisruptions', 'output',
        'catalog.min.json'))
    app.run()
