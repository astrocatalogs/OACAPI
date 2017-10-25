"""API for the Open Astronomy Catalogs."""
import json
import os

from collections import OrderedDict
from flask import Flask
from flask_restful import Api, Resource
from flask_compress import Compress

# Create a engine for connecting to SQLite3.
# Assuming salaries.db is in your app root folder

app = Flask(__name__)
Compress(app)
api = Api(app)

catdict = OrderedDict((
    ('sne', 'supernovae'),
    ('tde', 'tidaldisruptions'),
    ('kilonova', 'kilonovae')
))

catalogs = OrderedDict()

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

    def get(self, catalog_name, event_name, quantity_name=None, options=''):
        return Event().get(catalog_name, event_name, quantity_name, None, options, True)


class Event(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name, quantity_name=None, attribute_name=None, full=False, options=''):
        """Get result."""
        my_cat = None
        event = None

        # Options
        option_arr = list(filter(None, options.split('&')))
        option_arr = [x.split('=') for x in option_arr]
        option_arr = [tuple(option_arr[i] + [None]) if len(x) == 1 else tuple(option_arr[i]) for i, x in enumerate(option_arr)]
        options = OrderedDict(option_arr)

        fmt = options.get('format', 'json')
        mjd = options.get('mjd')

        # Attributes
        attribute_names = None
        if attribute_name is not None:
            attribute_names = attribute_name.split('+')

        # Prioritize catalog used to initiate query.
        for cat in catalogs:
            if cat != catalog_name:
                continue
            if event_name in catalogs[cat]:
                my_cat = cat

        # Try all other catalogs.
        if my_cat is None:
            for cat in catalogs:
                if cat == catalog_name:
                    continue
                if event_name in catalogs[cat]:
                    my_cat = cat

        if not my_cat:
            return {}

        if quantity_name and not full and catalogs[my_cat].get(event_name, {}).get(quantity_name) is not None:
            quantity = catalogs[my_cat][event_name][quantity_name]
            if attribute_names is None:
                return quantity
            return self.get_attributes(attribute_names, quantity)

        # When using the full data
        event = json.load(open(os.path.join(
            ac_path, catdict[my_cat], 'output', 'json',
            get_filename(event_name)), 'r'), object_pairs_hook=OrderedDict)

        if not quantity_name:
            if event:
                return event
        else:
            name = list(event.keys())[0]
            quantity = event[name].get(quantity_name, {})
            if attribute_names is None:
                return quantity
            return self.get_attributes(attribute_names, quantity)

        return {}

    def get_attributes(self, anames, quantity):
        if len(anames) == 1:
            return [x.get(anames[0]) for x in quantity if x.get(anames[0]) is not None]
        else:
            return [[x.get(a) for a in anames] for x in quantity if all([x.get(a) is not None for a in anames])]


api.add_resource(Catalogs, '/<string:catalog_name>/catalogs')
api.add_resource(Catalog, '/<string:catalog_name>/catalog')
api.add_resource(FullEvent,
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>?<string:options>',
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>/<string:attribute_name>?<string:options>')
api.add_resource(Event,
    '/<string:catalog_name>/event/<string:event_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>?<string:options>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>/<string:attribute_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>/<string:attribute_name>?<string:options>')

if __name__ == '__main__':
    print('Loading catalog...')
    for cat in catdict:
        catalogs[cat] = json.load(open(os.path.join(
            ac_path, catdict[cat], 'output', 'catalog.min.json'), 'r'),
            object_pairs_hook=OrderedDict)
        catalogs[cat] = dict(zip([x['name'] for x in catalogs[cat]], catalogs[cat]))
    app.run(threaded=True)
