"""API for the Open Astronomy Catalogs."""
import json
import os

from collections import OrderedDict
from flask import Flask, make_response, Response
from flask_restful import Api, Resource
from flask_compress import Compress

from flask import request
from werkzeug.contrib.fixers import ProxyFix

# Create a engine for connecting to SQLite3.
# Assuming salaries.db is in your app root folder

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
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
        use_full = False

        # Options
        fmt = request.values.get('format')
        fmt = fmt.lower() if fmt is not None else fmt
        if fmt == 'csv':
            delim = ','
        elif fmt == 'tsv':
            delim = '\t'

        mjd = request.values.get('mjd')
        incomplete = request.values.get('incomplete')

        if event_name is None:
            return catalogs.get(catalog_name, {})

        # Events
        event_names = event_name.split('+')

        if quantity_name is None:
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

        # Quantities
        quantity_names = quantity_name.split('+')

        have_quantity = False
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
                qdict = OrderedDict()
                for quantity in quantity_names:
                    qdict[quantity] = catalogs.get(my_cat, {}).get(my_event, {}).get(quantity, {})
                    if qdict[quantity] != {}:
                        have_quantity = True
                new_dict[event] = qdict
            if have_quantity:
                return new_dict
            use_full = True

        # Attributes
        if attribute_name is not None:
            attribute_names = attribute_name.split('+')

        if not use_full:
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
                qdict = OrderedDict()
                for quantity in quantity_names:
                    my_quantity = catalogs.get(my_cat, {}).get(my_event, {}).get(quantity, {})
                    qdict[quantity] = self.get_attributes(attribute_names, my_quantity, fmt, incomplete)
                new_dict[event] = qdict

            if fmt in ['csv', 'tsv']:
                # Determine which to use as axes in CSV/TSV file.
                rax = None
                cax = None
                axsub = {
                    'e': 'event',
                    'q': 'quantity',
                    'a': 'attribute'
                }
                if len(event_names) > 1:
                    rax = 'e'
                    if len(quantity_names) > 1:
                        cax = 'q'
                        if len(attribute_names) > 1:
                            return Response('{} not supported for this query type.'.format(fmt.upper()), mimetype='text/plain')
                    elif len(attribute_names) > 1:
                        cax = 'a'
                elif len(quantity_names) > 1:
                    rax = 'q'
                    if len(attribute_names) > 1:
                        cax = 'a'
                elif len(attribute_names) > 1:
                    rax = 'a'

                if rax == 'e':
                    rowheaders = event_names
                elif rax == 'q':
                    rowheaders = quantity_names
                elif rax == 'a':
                    rowheaders = attribute_names

                colheaders = None
                if cax == 'q':
                    colheaders = quantity_names
                elif cax == 'a':
                    colheaders = attribute_names

                if rax and cax:
                    rowheaders.insert(0, axsub[rax])

                outarr = [[]]
                print(rax, cax)
                print(new_dict)
                if rax == 'e':
                    if cax == 'q':
                        outarr = [[new_dict[e].get(q, '') for q in new_dict[e]] for e in new_dict]
                        outarr = [[q[0] if len(q) == 1 else delim.join(q) for q in e] for e in outarr]
                    else:
                        outarr = [[i for s in new_dict[e][quantity_name] for i in s] for e in new_dict]
                elif rax == 'q':
                    if cax == 'a':
                        print([len(new_dict[event_name][x]) for x in new_dict[event_name]])
                        outarr = [[i for s in new_dict[event_name][x] for i in s] if len(new_dict[event_name][x]) == 1 else [
                            delim.join(i) for i in list(map(list, zip(*new_dict[event_name][x])))] for x in new_dict[event_name]]
                    else:
                        outarr = [new_dict[event_name][x] if len(new_dict[event_name][x]) == 1 else [delim.join(new_dict[event_name][x])] for x in new_dict[event_name]]
                elif rax == 'a':
                    outarr = new_dict[event_name][quantity_name]
                else:
                    return new_dict[event_name][quantity_name]

                outarr = [[('"' + x + '"') if delim in x else x for x in y] for y in outarr]

                if rax is not None and cax is None:
                    cax = rax
                    rax = None
                    colheaders = rowheaders
                    rowheaders = None
                    outarr = list(map(list, zip(*outarr)))

                if colheaders:
                    outarr.insert(0, colheaders)
                if rowheaders:
                    for i, row in enumerate(outarr):
                        outarr[i].insert(0, rowheaders[i])

                return Response('\n'.join([delim.join(y) for y in outarr]), mimetype='text/plain')

            return new_dict

        # When using the full data
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

        event = json.load(open(os.path.join(
            ac_path, catdict[my_cat], 'output', 'json',
            get_filename(event_name)), 'r'), object_pairs_hook=OrderedDict)

        if not quantity_name:
            if event:
                return event
        else:
            name = list(event.keys())[0]
            quantity = event[name].get(quantity_name, {})
            if attribute_name is None:
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
