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
aliases = OrderedDict()

ac_path = os.path.join('/root', 'astrocats', 'astrocats')

def get_filename(name):
    return name.replace('/', '_') + '.json'

class Info(Resource):
    """Return basic info about catalog."""

    _infotxt = open('info.html', 'r').read()

    def get(self, catalog_name):
        """Return HTML page."""
        route_msg = ''
        if catalog_name != 'astrocats':
            route_msg = 'For this particular route, events from the "{}" catalog will be matched against first.'.format(catdict.get(catalog_name))
        itxt = self._infotxt.replace('$ROUTE_MSG', route_msg)
        return Response(itxt, mimetype='text/html')


class Catalogs(Resource):
    """Return all catalogs."""

    def get(self, catalog_name):
        """Get result."""
        return catalogs

class Catalog(Resource):
    """Return whole catalog."""

    def get(self, catalog_name, event_name):
        """Get result."""


class FullEvent(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name, quantity_name=None):
        return Event().get(catalog_name, event_name, quantity_name, None, True)


class Event(Resource):
    """Return single event."""

    def get(self, catalog_name, event_name=None, quantity_name=None, attribute_name=None, full=False):
        """Get result."""
        event = None

        # Options
        fmt = request.values.get('format')
        fmt = fmt.lower() if fmt is not None else fmt
        if fmt in ['csv', 'tsv'] and attribute_name is None:
            return Response('{} not supported for this query type.'.format(fmt.upper()), mimetype='text/plain')

        mjd = request.values.get('mjd')
        incomplete = request.values.get('incomplete')

        if event_name is None:
            return catalogs.get(catalog_name, {})

        # Events
        event_names = event_name.split('+')

        if attribute_name is None:
            new_dict = OrderedDict()
            for event in event_names:
                my_cat, my_event = None, None
                alopts = aliases.get(event, [])
                for opt in alopts:
                    if opt[0] == catalog_name:
                        my_cat, my_event = tuple(opt)
                if not my_cat:
                    for opt in alopts:
                        if opt[0] != catalog_name:
                            my_cat, my_event = tuple(opt)
                new_dict[event] = catalogs.get(my_cat, {}).get(my_event, {})
            return new_dict

        # Attributes
        attribute_names = attribute_name.split('+')

        # Prioritize catalog used to initiate query.
        my_cat = ''
        if event_name in catalogs[catalog_name]:
            my_cat = catalog_name
        else:
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
            return self.get_attributes(attribute_names, quantity, fmt, incomplete)

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
            return self.get_attributes(attribute_names, quantity, fmt, incomplete)

        return {}

    def get_attributes(self, anames, quantity, fmt='json', incomplete=None):
        if len(anames) == 1:
            attributes = [x.get(anames[0]) for x in quantity if x.get(anames[0]) is not None]
        else:
            if incomplete is not None:
                attributes = [[x.get(a, '') for a in anames] for x in quantity if any([x.get(a) is not None for a in anames])]
            else:
                attributes = [[x.get(a) for a in anames] for x in quantity if all([x.get(a) is not None for a in anames])]

        if fmt == 'csv':
            return Response('\n'.join([','.join(anames)] + [','.join(x) for x in attributes]), mimetype='text/plain')
        if fmt == 'tsv':
            return Response('\n'.join(['\t'.join(anames)] + ['\t'.join(x) for x in attributes]), mimetype='text/plain')

        return attributes


api.add_resource(Info, '/<string:catalog_name>/')
api.add_resource(Catalogs, '/<string:catalog_name>/catalogs')
api.add_resource(FullEvent,
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>/<string:attribute_name>')
api.add_resource(Event,
    '/<string:catalog_name>/catalog',
    '/<string:catalog_name>/<string:event_name>',
    '/<string:catalog_name>/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/<string:event_name>/<string:quantity_name>/<string:attribute_name>')

if __name__ == '__main__':
    print('Loading catalog...')
    for cat in catdict:
        catalogs[cat] = json.load(open(os.path.join(
            ac_path, catdict[cat], 'output', 'catalog.min.json'), 'r'),
            object_pairs_hook=OrderedDict)
        catalogs[cat] = dict(zip([x['name'] for x in catalogs[cat]], catalogs[cat]))
    print('Creating alias dictionary...')
    for cat in catdict:
        for event in catalogs[cat]:
            laliases = catalogs[cat].get(event, {}).get('alias', [])
            laliases = list(set([event] + [x['value'] for x in laliases]))
            for alias in laliases:
                aliases.setdefault(alias, []).append([cat, event])
    print('Launching API...')
    app.run(threaded=True)
