"""API for the Open Astronomy Catalogs."""
import json
import os
import re
from collections import OrderedDict
from timeit import default_timer as timer

import numpy as np
import logging
from astropy import units as un
from astropy.coordinates import SkyCoord as coord
from six import string_types
from werkzeug.contrib.fixers import ProxyFix

from flask import Flask, Response, request
from flask_compress import Compress
from flask_restful import Api, Resource

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
coo = None
rdnames = []

ac_path = os.path.join('/root', 'astrocats', 'astrocats')

raregex = re.compile("^[0-9]{1,2}:[0-9]{2}(:?[0-9]{2}\.?([0-9]+)?)?$")
decregex = re.compile("^[+-]?[0-9]{1,2}:[0-9]{2}(:?[0-9]{2}\.?([0-9]+)?)?$")

logger = logging.getLogger('gunicorn.error')
logger.setLevel(logging.INFO)

def is_number(s):
    """Check if input is a number."""
    if isinstance(s, list) and not isinstance(s, string_types):
        try:
            for x in s:
                if isinstance(x, string_types) and ' ' in x:
                    raise ValueError
            [float(x) for x in s]
            return True
        except ValueError:
            return False
    else:
        try:
            if isinstance(s, string_types) and ' ' in s:
                raise ValueError
            float(s)
            return True
        except ValueError:
            return False


def is_list(x):
    """Check if object is a list (but not a string)."""
    return isinstance(x, list) and not isinstance(x, string_types)


def listify(x):
    """Return variable in a list if not already a list."""
    if not is_list(x):
        return [x]
    return x


def get_filename(name):
    """Return filename for astrocats event."""
    return name.replace('/', '_') + '.json'


def bool_str(x):
    """Return T or F for a bool."""
    return 'T' if x else 'F'


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
    """Return single event."""

    _ANGLE_LIMIT = 36000.0
    _EXPENSIVE = {
        'spectra': ['data']
    }
    _EXPENSIVE_LIMIT = 100
    _NO_CSV = ['data']
    _FULL_LIMIT = 1000
    _AXSUB = {
        'e': 'event',
        'q': 'quantity',
        'a': 'attribute'
    }
    _SPECIAL_ATTR = set([
        'format',
        'ra',
        'dec',
        'radius',
        'complete',
        'first',
        'closest',
        'item'
    ])

    def get(self, catalog_name, event_name=None, quantity_name=None,
            attribute_name=None):
        """Get result."""
        logger.info('Query from {}: {} -- {}/{}/{}'.format(
            request.remote_addr, catalog_name, event_name, quantity_name,
            attribute_name))
        logger.info('Arguments: ' + ', '.join(['='.join(x)
                                         for x in request.args.items()]))
        start = timer()
        result = self.retrieve(catalog_name, event_name,
                               quantity_name, attribute_name, False)
        end = timer()
        logger.info('Time to perform query: {}s'.format(end - start))
        return result

    def retrieve(self, catalog_name, event_name=None, quantity_name=None,
                 attribute_name=None, full=False):
        """Retrieve data, first trying catalog file then event files."""
        event = None
        use_full = full
        ename = event_name

        # Options
        if not use_full:
            rfull = request.values.get('full')
            if rfull is not None:
                return self.retrieve(
                    catalog_name, ename, quantity_name, attribute_name, True)

        fmt = request.values.get('format')
        fmt = fmt.lower() if fmt is not None else fmt

        ra = request.values.get('ra')
        dec = request.values.get('dec')
        radius = request.values.get('radius')
        complete = request.values.get('complete')
        first = request.values.get('first')
        closest = request.values.get('closest')

        include_keys = list(set(request.args.keys()) - self._SPECIAL_ATTR)
        includes = OrderedDict()
        for key in include_keys:
            includes[key] = request.values.get(key)

        excludes = OrderedDict([('realization', '')])

        if first is None:
            item = request.values.get('item')
            try:
                item = int(item)
            except Exception:
                item = None
        else:
            item = 0
        if radius is not None:
            try:
                radius = float(radius)
            except Exception:
                radius = 0.0
            if radius >= self._ANGLE_LIMIT:
                return {'message': 'Angle limited to {} degrees.'.format(
                    self._ANGLE_LIMIT / 3600.)}

        if ename is None:
            if ra is not None and dec is not None:
                lcoo = coord(ra, dec, unit=(un.hourangle, un.deg))
                idxcat = np.where(lcoo.separation(coo) <=
                                  radius * un.arcsecond)[0]
                if len(idxcat):
                    ename = '+'.join([rdnames[i].replace('+', '$PLUS$')
                                      for i in idxcat])
            if ename is None:
                return catalogs.get(catalog_name, {})

        if fmt is not None and (
                ename is None or quantity_name is None or
                attribute_name is None):
            return Response((
                'Error: "{}" format only supported if event name, quantity, '
                'and attribute are specified (e.g. '
                'SN2014J/photometry/magnitude).').format(
                    fmt), mimetype='text/plain')
        # Events
        event_names = [] if ename is None else ename.split('+')
        event_names = [x.replace('$PLUS$', '+') for x in event_names]

        # Quantities
        quantity_names = [
        ] if quantity_name is None else quantity_name.split('+')

        # Attributes. Always append source.
        attribute_names = [
        ] if attribute_name is None else attribute_name.split('+')

        if use_full and len(event_names) > self._FULL_LIMIT:
            return {'message': 'Maximum event limit ({}) exceeded'.format(
                self._FULL_LIMIT)}

        if fmt is not None and any([n in attribute_names
                                    for n in self._NO_CSV]):
            return {'message': 'This query does not support delimited output'}

        if len(event_names) > self._EXPENSIVE_LIMIT:
            for quantity in quantity_names:
                for exp in self._EXPENSIVE:
                    if any([e in attribute_names for e in self._EXPENSIVE]):
                        return {'message': 'Too expensive.'}

        edict = OrderedDict()
        fcatalogs = OrderedDict()
        sources = OrderedDict()
        for event in event_names:
            my_cat, my_event = None, None
            alopts = aliases.get(event.lower().replace(
                ' ', '').replace('-', ''), [])
            for opt in alopts:
                if opt[0] == catalog_name:
                    my_cat, my_event, my_alias = tuple(opt)
            if not my_cat:
                for opt in alopts:
                    if opt[0] != catalog_name:
                        my_cat, my_event, my_alias = tuple(opt)
            if full:
                if not my_cat:
                    return {'message': 'Event not found in any catalog.'}
                fcatalogs.update(json.load(
                    open(os.path.join(
                        ac_path, catdict[my_cat], 'output', 'json',
                        get_filename(my_event)), 'r'),
                    object_pairs_hook=OrderedDict))
                sources[my_event] = [x.get('bibcode', x.get('arxivid', x.get('name')))
                    for x in fcatalogs[my_event].get('sources')]
            if quantity_name is None:
                if full:
                    edict[event] = fcatalogs.get(my_event, {})
                else:
                    edict[event] = catalogs.get(my_cat, {}).get(my_event, {})
            else:
                qdict = OrderedDict()
                for quantity in quantity_names:
                    if full:
                        my_quantity = fcatalogs.get(
                            my_event, {}).get(quantity, {})
                    else:
                        my_quantity = catalogs.get(my_cat, {}).get(
                            my_event, {}).get(quantity, {})
                    closest_locs = []
                    if closest is not None:
                        closest_locs = list(sorted(list(set([
                            np.argmin([abs(np.mean([float(y)
                                                    for y in listify(x.get(i))]) -
                                           float(includes[i])) for x in my_quantity])
                            for i in includes if len(my_quantity) and
                            is_number(includes[i]) and
                            all([is_number(x.get(i)) for x in my_quantity])]))))

                    if attribute_name is None:
                        if full:
                            qdict[quantity] = [x for xi, x in enumerate(my_quantity) if
                                not len(closest_locs) or xi in closest_locs]
                        else:
                            qdict[quantity] = [x for xi, x in enumerate(my_quantity) if
                                not len(closest_locs) or xi in closest_locs]
                        if item is not None:
                            try:
                                qdict[quantity] = qdict[quantity][item]
                            except Exception:
                                pass
                    else:
                        qdict[quantity] = self.get_attributes(
                            attribute_names, my_quantity, complete, item,
                            includes=includes, excludes=excludes,
                            closest_locs=closest_locs,
                            sources=np.array(sources.get(my_event, [])))

                    if not qdict[quantity]:
                        use_full = True
                        break
                if not full and use_full:
                    break
                edict[event] = qdict

        if not full and use_full:
            return self.retrieve(
                catalog_name, ename, quantity_name, attribute_name, True)

        if fmt is not None:
            return self.get_dsv(
                edict, event_names, quantity_names, attribute_names, fmt)

        return edict

    def get_attributes(
        self, anames, quantity, complete=None, item=None, includes={},
            excludes={}, closest_locs=[], sources=[]):
        """Return array of attributes."""

        if complete is None:
            attributes = [
                [','.join(sources[[int(y) for y in x.get(a, '').split(',')]]) if a == 'source' else x.get(a, '') for a in anames]
                for xi, x in enumerate(quantity) if any(
                    [x.get(a) is not None for a in anames]) and (
                    (len(closest_locs) and xi in closest_locs) or
                    all([i in x if (includes.get(i) == '') else (includes.get(i) == x.get(i)) for i in includes])) and
                    not any([e in x if (excludes.get(e) == '') else (excludes.get(e) == x.get(e)) for e in excludes])]
        else:
            attributes = [
                [','.join(sources[[int(y) for y in x.get(a, '').split(',')]]) if a == 'source' else x.get(a, '') for a in anames]
                for xi, x in enumerate(quantity) if all(
                    [x.get(a) is not None for a in anames]) and (
                    (len(closest_locs) and xi in closest_locs) or
                    all([i in x if (includes.get(i) == '') else (includes.get(i) == x.get(i)) for i in includes])) and
                    not any([e in x if (excludes.get(e) == '') else (excludes.get(e) == x.get(e)) for e in excludes])]

        if item is not None:
            try:
                attributes = [attributes[item]]
            except Exception:
                pass

        return attributes

    def get_dsv(self, edict, enames, qnames, anames, fmt='csv'):
        """Get delimited table."""
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
                colheaders.insert(0, self._AXSUB[rax])

        if rax and cax:
            rowheaders.insert(0, self._AXSUB[rax])

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
                outarr = [i for s in [
                    [[enames[ei]] + q for q in edict[e][qname]]
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

        boolrows = [any([isinstance(x, bool) for x in y])
                    for y in list(map(list, zip(*outarr)))]
        outarr = [[bool_str(x) if boolrows[xi] else (
            ('"' + x + '"') if delim in x else x) for xi, x in enumerate(y)]
            for y in outarr]

        if cax is None:
            cax, rax = rax, None
            colheaders, rowheaders = list(rowheaders), None

        if colheaders:
            outarr.insert(0, colheaders)
        if rowheaders and not (rax == 'e' and cax == 'a'):
            for i, row in enumerate(outarr):
                outarr[i].insert(0, rowheaders[i])

        return Response('\n'.join([
            delim.join([
                ('"' + delim.join(z) + '"') if is_list(
                    z) else z for z in y])
            for y in outarr]), mimetype='text/plain')


cn = '<string:catalog_name>'
en = '<string:event_name>'
qn = '<string:quantity_name>'
an = '<string:attribute_name>'

# api.add_resource(Info, '/<string:catalog_name>/')
api.add_resource(Catalogs, '/'.join(['', cn, 'catalogs']))
api.add_resource(
    Catalog,
    '/'.join(['', cn]),
    '/'.join(['', cn]) + '/',
    '/'.join(['', cn, 'catalog']),
    '/'.join(['', cn, 'catalog']) + '/',
    '/'.join(['', cn, 'all', qn]),
    '/'.join(['', cn, 'all', qn]) + '/',
    '/'.join(['', cn, 'all', qn, an]),
    '/'.join(['', cn, 'all', qn, an]) + '/',
    '/'.join(['', cn, 'event', en]),
    '/'.join(['', cn, 'event', en]) + '/',
    '/'.join(['', cn, 'event', en, qn]),
    '/'.join(['', cn, 'event', en, qn]) + '/',
    '/'.join(['', cn, 'event', en, qn, an]),
    '/'.join(['', cn, 'event', en, qn, an]) + '/',
    '/'.join(['', cn, en]),
    '/'.join(['', cn, en]) + '/',
    '/'.join(['', cn, en, qn]),
    '/'.join(['', cn, en, qn]) + '/',
    '/'.join(['', cn, en, qn, an]),
    '/'.join(['', cn, en, qn, an]) + '/')

logger.info('Loading catalog...')
for cat in catdict:
    catalogs[cat] = json.load(open(os.path.join(
        ac_path, catdict[cat], 'output', 'catalog.min.json'), 'r'),
        object_pairs_hook=OrderedDict)
    catalogs[cat] = dict(zip([x['name']
                              for x in catalogs[cat]], catalogs[cat]))
logger.info('Creating alias dictionary and position arrays...')
ras = []
decs = []
for cat in catdict:
    for event in catalogs[cat]:
        levent = catalogs[cat].get(event, {})
        laliases = levent.get('alias', [])
        laliases = list(set([event] + [x['value'] for x in laliases]))
        for alias in laliases:
            aliases.setdefault(alias.lower().replace(' ', '').replace(
                '-', ''), []).append([cat, event, alias])
        lra = levent.get('ra')
        ldec = levent.get('dec')
        if lra is None and ldec is None:
            continue
        lra = lra[0].get('value')
        ldec = ldec[0].get('value')
        if lra is None or ldec is None:
            continue
        if not raregex.match(lra) or not decregex.match(ldec):
            continue
        rdnames.append(event)
        ras.append(lra)
        decs.append(ldec)

coo = coord(ras, decs, unit=(un.hourangle, un.deg))

logger.info('Launching API...')
# app.run()
