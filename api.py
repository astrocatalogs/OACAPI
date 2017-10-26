"""API for the Open Astronomy Catalogs."""
import json
import os

from collections import OrderedDict
from flask import Flask, make_response, Response
from flask_restful import Api, Resource
from flask_compress import Compress

from flask import request

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

    def get(self, catalog_name, event_name, quantity_name=None):
        return Event().get(catalog_name, event_name, quantity_name, None, True)


class Event(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name, quantity_name=None, attribute_name=None, full=False):
        """Get result."""
        my_cat = None
        event = None

        # Options
        fmt = request.values.get('format')
        mjd = request.values.get('mjd')

        print(fmt, attribute_name)

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
            return self.get_attributes(attribute_names, quantity, fmt)

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
            return self.get_attributes(attribute_names, quantity, fmt)

        return {}

    def get_attributes(self, anames, quantity, fmt='json'):
        if len(anames) == 1:
            attributes = [x.get(anames[0]) for x in quantity if x.get(anames[0]) is not None]
        else:
            attributes = [[x.get(a) for a in anames] for x in quantity if all([x.get(a) is not None for a in anames])]

        if fmt == 'csv':
            return Response('\n'.join([','.join(x) for x in attributes]), mimetype='text/plain')
        if fmt == 'tsv':
            return Response('\n'.join(['\t'.join(x) for x in attributes]), mimetype='text/plain')

        return attributes


api.add_resource(Catalogs, '/<string:catalog_name>/catalogs')
api.add_resource(Catalog, '/<string:catalog_name>/catalog')
api.add_resource(FullEvent,
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>/<string:attribute_name>')
api.add_resource(Event,
    '/<string:catalog_name>/event/<string:event_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>/<string:attribute_name>')

if __name__ == '__main__':
    print('Loading catalog...')
    for cat in catdict:
        catalogs[cat] = json.load(open(os.path.join(
            ac_path, catdict[cat], 'output', 'catalog.min.json'), 'r'),
            object_pairs_hook=OrderedDict)
        catalogs[cat] = dict(zip([x['name'] for x in catalogs[cat]], catalogs[cat]))
    app.run(threaded=True)
