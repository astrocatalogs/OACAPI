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

    def get(self, catalog_name, event_name, quantity_name=None):
        return Event().get(catalog_name, event_name, quantity_name, None, True)


class ValueEvent(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name, quantity_name=None, attribute_name='value', item=0):
        return Event().get(catalog_name, event_name, quantity_name, attribute_name, item)


class Event(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name, quantity_name=None, attribute_name=None, item=None, full=False):
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

        if quantity_name and not full and catalogs[my_cat].get(event_name, {}).get(quantity_name):
            quantity = catalogs[my_cat][event_name][quantity_name]
            if attribute_name is not None and item is not None and attribute_name in quantity[item]:
                return quantity[item][attribute_name]
            else:
                return quantity

        event = json.load(open(os.path.join(
            ac_path, catdict[my_cat], 'output', 'json',
            get_filename(event_name)), 'r'))

        if not quantity_name:
            if event:
                return event
        else:
            name = list(event.keys())[0]
            quantity = event[name].get(quantity_name, {})
            if attribute_name is not None and quantity_name in quantity[attribute_name]:
                return quantity[attribute_name][quantity_name]
            else:
                return quantity

        return {}


api.add_resource(Catalogs, '/<string:catalog_name>/catalogs')
api.add_resource(Catalog, '/<string:catalog_name>/catalog')
api.add_resource(Event, '/<string:catalog_name>/event/<string:event_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>')
api.add_resource(FullEvent, '/<string:catalog_name>/event/<string:event_name>/full',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>/full')
api.add_resource(ValueEvent, '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>/<string:attribute_name>',
    '/<string:catalog_name>/event/<string:event_name>'
    '/<string:quantity_name>/<string:attribute_name>/<int:item>')

if __name__ == '__main__':
    print('Loading catalog...')
    for cat in catdict:
        catalogs[cat] = json.load(open(os.path.join(
            ac_path, catdict[cat], 'output', 'catalog.min.json'), 'r'))
        catalogs[cat] = dict(zip([x['name'] for x in catalogs[cat]], catalogs[cat]))
    app.run(threaded=True)
