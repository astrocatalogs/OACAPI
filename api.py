"""API for the Open Astronomy Catalogs."""
import json
import os

from flask import Flask
from flask_restful import Api, Resource
from flask_compress import Compress

# Create a engine for connecting to SQLite3.
# Assuming salaries.db is in your app root folder

app = Flask(__name__)
Compress(app)
api = Api(app)

catdict = {
    'sne': 'supernovae',
    'tde': 'tidaldisruptions',
    'kilonova': 'kilonovae'
}

catalogs = {}

ac_path = os.path.join('/root', 'astrocats', 'astrocats')

def get_filename(name):
    return name.replace('/', '_') + '.json'

class Catalogs(Resource):
    """Return all catalogs."""

    def get(self):
        """Get result."""
        return catalogs

class Catalog(Resource):
    """Return whole catalog."""

    def get(self, catalog_name):
        """Get result."""
        return catalogs.get(catdict.get(catalog_name, ''), {})


class FullEvent(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name, attribute=None):
        return Event().get(catalog_name, event_name, attribute, True)


class Event(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name, attribute=None, full=False):
        """Get result."""
        my_cat = None
        event = None
        # Prioritize catalog used to initiate query.
        for cat in catalogs:
            if cat != catalog_name:
                continue
            if event_name in catalogs[cat]:
                my_cat = cat

        # Try all other catalogs.
        for cat in catalogs:
            if cat == catalog_name:
                continue
            if event_name in catalogs[cat]:
                my_cat = cat

        if not my_cat:
            return {}

        if attribute and not full and catalogs[my_cat].get(event_name, {}).get(attribute):
            return catalogs[my_cat][event_name][attribute]

        event = json.load(open(os.path.join(
            ac_path, catdict[my_cat], 'output', 'json',
            get_filename(event_name)), 'r'))

        if not attribute:
            if event:
                return event
        else:
            name = list(event.keys())[0]
            return(event[name].get(attribute, {}))

        return {}


api.add_resource(Catalogs, '/<string:catalog_name>/catalogs')
api.add_resource(Catalog, '/<string:catalog_name>/catalog')
api.add_resource(Event, '/<string:catalog_name>/event/<string:event_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:attribute>')
api.add_resource(FullEvent, '/<string:catalog_name>/event/<string:event_name>/full',
    '/<string:catalog_name>/event/<string:event_name>/<string:attribute>/full')

if __name__ == '__main__':
    print('Loading catalog...')
    for cat in catdict:
        catalogs[cat] = json.load(open(os.path.join(
            ac_path, catdict[cat], 'output', 'catalog.min.json'), 'r'))
        catalogs[cat] = dict(zip([x['name'] for x in catalogs[cat]], catalogs[cat]))
    app.run()
