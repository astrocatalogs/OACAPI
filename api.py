"""API for the Open Astronomy Catalogs."""
import json
import os
from collections import OrderedDict

from werkzeug.contrib.fixers import ProxyFix

from flask import Flask, Response, request
from flask_compress import Compress
from flask_restful import Api, Resource
from six import string_types

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


def is_list(x):
    return isinstance(x, list) and not isinstance(x, string_types)

def listify(x):
    """Return variable in a list if not already a list."""
    if not is_list(x):
        return [x]
    return x

def get_filename(name):
    """Return filename for astrocats event."""
    return name.replace('/', '_') + '.json'


class Info(Resource):
    """Return basic info about catalog."""

    _infotxt = open('info.html', 'r').read()

    def get(self, catalog_name):
        """Return HTML page."""
        route_msg = ''
        if catalog_name != 'astrocats':
            route_msg = (
                'For this particular route, events from the "{}" '
                'catalog will be matched against first.').format(
                catdict.get(catalog_name))
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

    def get(self, catalog_name, event_name, quantity_name=None, attribute_name=None):
        """Pass-through to `Event` with `full = True`."""
        return Event().get(catalog_name, event_name=event_name,
            quantity_name=quantity_name, attribute_name=attribute_name, full=True)


class Event(Resource):
    """Return single event."""

    _axsub = {
        'e': 'event',
        'q': 'quantity',
        'a': 'attribute'
    }

    def get(self, catalog_name, event_name=None, quantity_name=None,
            attribute_name=None, full=False):
        """Get result."""
        return self.retrieve(catalog_name, event_name, quantity_name, attribute_name, full)

    def retrieve(self, catalog_name, event_name=None, quantity_name=None,
            attribute_name=None, full=False):
        """Retrieve data, first trying catalog file then event files."""
        event = None
        use_full = full

        # Options
        fmt = request.values.get('format')
        fmt = fmt.lower() if fmt is not None else fmt

        mjd = request.values.get('mjd')
        complete = request.values.get('complete')
        first = request.values.get('first')
        if first is None:
            item = request.values.get('item')
            try:
                item = int(item)
            except Exception:
                item = None
        else:
            item = 0

        if event_name is None:
            return catalogs.get(catalog_name, {})

        if fmt is not None and (event_name is None or
                quantity_name is None or attribute_name is None):
            return Response((
                'Error: "{}" format only supported if event name, quantity, '
                'and attribute are specified (e.g. '
                'SN2014J/photometry/magnitude).').format(fmt), mimetype='text/plain')
        # Events
        event_names = [] if event_name is None else event_name.split('+')

        # Quantities
        quantity_names = [] if quantity_name is None else quantity_name.split('+')

        # Attributes
        attribute_names = [] if attribute_name is None else attribute_name.split('+')

        edict = OrderedDict()
        fcatalogs = OrderedDict()
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
            if full:
                fcatalogs.update(json.load(open(os.path.join(
                    ac_path, catdict[my_cat], 'output', 'json',
                    get_filename(my_event)), 'r'), object_pairs_hook=OrderedDict))
            if quantity_name is None:
                if full:
                    edict[event] = fcatalogs.get(my_event, {})
                else:
                    edict[event] = catalogs.get(my_cat, {}).get(my_event, {})
            else:
                qdict = OrderedDict()
                for quantity in quantity_names:
                    if attribute_name is None:
                        if full:
                            qdict[quantity] = fcatalogs.get(
                                my_event, {}).get(quantity, {})
                        else:
                            qdict[quantity] = catalogs.get(my_cat, {}).get(
                                my_event, {}).get(quantity, {})
                        if item is not None:
                            try:
                                qdict[quantity] = qdict[quantity][item]
                            except Exception:
                                pass
                    else:
                        if full:
                            my_quantity = fcatalogs.get(
                                my_event, {}).get(quantity, {})
                        else:
                            my_quantity = catalogs.get(my_cat, {}).get(
                                my_event, {}).get(quantity, {})
                        qdict[quantity] = self.get_attributes(
                            attribute_names, my_quantity, complete, item)
                    if not qdict[quantity]:
                        use_full = True
                        break
                if not full and use_full:
                    break
                edict[event] = qdict

        if not full and use_full:
            edict = self.retrieve(catalog_name, event_name, quantity_name, attribute_name, True)

        if not full and fmt is not None:
            return self.get_dsv(edict, event_names, quantity_names, attribute_names, fmt)

        return edict

    def get_attributes(self, anames, quantity, complete=None, item=None):
        """Return array of attributes."""
        if complete is None:
            attributes = [
                [x.get(a, '') for a in anames] for x in quantity if any(
                    [x.get(a) is not None for a in anames])]
        else:
            attributes = [
                [x.get(a, '') for a in anames] for x in quantity if all(
                    [x.get(a) is not None for a in anames])]

        if item is not None:
            try:
                attributes = [attributes[item]]
            except Exception:
                pass

        return attributes

    def get_dsv(self, edict, enames, qnames, anames, fmt='csv'):
        if fmt not in ['csv', 'tsv']:
            return Response('Unknown format.', mimetype='text/plain')
        # Determine which to use as axes in CSV/TSV file.
        rax = None
        cax = None

        ename = enames[0]
        qname = qnames[0]

        if fmt == 'csv':
            delim = ','
        elif fmt == 'tsv':
            delim = '\t'

        if len(enames) > 1:
            rax = 'e'
            if len(qnames) > 1:
                cax = 'q'
                if len(anames) > 1:
                    return Response(
                        '{} not supported for this query type.'.format(
                            fmt.upper()), mimetype='text/plain')
            elif len(anames) > 0:
                cax = 'a'
        elif len(qnames) > 1:
            rax = 'q'
            if len(anames) > 0:
                cax = 'a'
        elif len(anames) > 1:
            rax = 'a'

        rowheaders = None
        if rax == 'e':
            rowheaders = list(enames)
        elif rax == 'q':
            rowheaders = list(qnames)
        else:
            rowheaders = list(anames)

        colheaders = None
        if cax == 'q':
            colheaders = list(qnames)
        elif cax == 'a':
            colheaders = list(anames)
            if rax == 'e':
                colheaders.insert(0, self._axsub[rax])

        if rax and cax:
            rowheaders.insert(0, self._axsub[rax])

        outarr = [[]]
        if rax == 'e':
            if cax == 'q':
                outarr = [
                    [edict[e].get(q, '') for q in edict[
                        e]] for e in edict]
                outarr = [[[delim.join(a) if is_list(a) else a
                    for a in q] for q in e] for e in outarr]
                outarr = [[delim.join(q) if is_list(q) else q
                    for q in e] for e in outarr]
            elif cax == 'a':
                #outarr = [[i for s in edict[e][qname]
                #           for i in s] for e in edict]
                outarr = [i for s in [[[enames[ei]] + q for q in edict[e][qname]]
                    for ei, e in enumerate(edict)] for i in s]
            else:
                outarr = [edict[e][qname] for e in edict]
        elif rax == 'q':
            if cax == 'a':
                outarr = [
                    [i for s in edict[ename][x] for i in s]
                    if len(edict[ename][x]) == 1 else [
                        delim.join(i) for i in list(map(
                            list, zip(*edict[ename][x])))]
                    for x in edict[ename]]
            else:
                outarr = [edict[ename][x] if len(
                    edict[ename][x]) == 1 else [
                    delim.join(edict[ename][x])]
                    for x in edict[ename]]
        elif rax == 'a':
            outarr = edict[ename][qname]
        else:
            outarr = listify(edict[ename][qname])

        outarr = [[('"' + x + '"') if delim in x else x for x in y]
                  for y in outarr]

        if cax is None:
            #if rax is None:
            #    outarr = list(map(list, zip(*outarr)))
            cax, rax = rax, None
            colheaders, rowheaders = list(rowheaders), None

        if colheaders:
            outarr.insert(0, colheaders)
        if rowheaders and not (rax == 'e' and cax == 'a'):
            for i, row in enumerate(outarr):
                outarr[i].insert(0, rowheaders[i])

        return Response('\n'.join(
            [delim.join(y) for y in outarr]), mimetype='text/plain')


api.add_resource(Info, '/<string:catalog_name>/')
api.add_resource(Catalogs, '/<string:catalog_name>/catalogs')
api.add_resource(
    FullEvent,
    '/<string:catalog_name>/full/<string:event_name>',
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/full/<string:event_name>/<string:quantity_name>/<string:attribute_name>')
api.add_resource(
    Event,
    '/<string:catalog_name>/catalog',
    '/<string:catalog_name>/event/<string:event_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/event/<string:event_name>/<string:quantity_name>/<string:attribute_name>',
    '/<string:catalog_name>/<string:event_name>',
    '/<string:catalog_name>/<string:event_name>/<string:quantity_name>',
    '/<string:catalog_name>/<string:event_name>/<string:quantity_name>/<string:attribute_name>')

if __name__ == '__main__':
    print('Loading catalog...')
    for cat in catdict:
        catalogs[cat] = json.load(open(os.path.join(
            ac_path, catdict[cat], 'output', 'catalog.min.json'), 'r'),
            object_pairs_hook=OrderedDict)
        catalogs[cat] = dict(zip([x['name']
                                  for x in catalogs[cat]], catalogs[cat]))
    print('Creating alias dictionary...')
    for cat in catdict:
        for event in catalogs[cat]:
            laliases = catalogs[cat].get(event, {}).get('alias', [])
            laliases = list(set([event] + [x['value'] for x in laliases]))
            for alias in laliases:
                aliases.setdefault(alias, []).append([cat, event])
    print('Launching API...')
    app.run(threaded=True)
