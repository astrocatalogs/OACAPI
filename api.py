"""API for the Open Astronomy Catalogs."""
import json
import logging
import os
import re
from collections import OrderedDict
from timeit import default_timer as timer

import numpy as np
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
        'width',
        'height',
        'complete',
        'first',
        'closest',
        'item'
    ])

    def post(self, *args, **kwargs):
        """Handle POST request."""
        return self.get(*args, **kwargs), 200

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
        search_all = False
        ename = event_name
        qname = quantity_name
        aname = attribute_name

        req_vals = request.get_json()
        
        if not req_vals:
            req_vals = request.values

        # Load event/quantity/attribute if provided by request.
        event_req = req_vals.get('event')
        quantity_req = req_vals.get('quantity')
        attribute_req = req_vals.get('attribute')
        if ename is None and event_req is not None:
            if not isinstance(event_req, string_types):
                ename = '+'.join(listify(event_req))
            else:
                ename = event_req
        if qname is None and quantity_req is not None:
            if not isinstance(quantity_req, string_types):
                qname = '+'.join(listify(quantity_req))
            else:
                qname = quantity_req
        if aname is None and attribute_req is not None:
            if not isinstance(attribute_req, string_types):
                aname = '+'.join(listify(attribute_req))
            else:
                aname = attribute_req

        # Options
        if not use_full:
            rfull = req_vals.get('full')
            if rfull is not None:
                return self.retrieve(
                    catalog_name, ename, qname, aname, True)

        fmt = req_vals.get('format')
        fmt = fmt.lower() if fmt is not None else fmt

        ra = req_vals.get('ra')
        dec = req_vals.get('dec')
        radius = req_vals.get('radius')
        width = req_vals.get('width')
        height = req_vals.get('height')
        complete = req_vals.get('complete')
        first = req_vals.get('first')
        closest = req_vals.get('closest')

        include_keys = list(
            sorted(set(request.args.keys()) - self._SPECIAL_ATTR))
        includes = OrderedDict()
        for key in include_keys:
            includes[key] = req_vals.get(key)

        excludes = OrderedDict([('realization', '')])

        if first is None:
            item = req_vals.get('item')
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
                return {'message': 'Radius limited to {} degrees.'.format(
                    self._ANGLE_LIMIT / 3600.)}
        if width is not None:
            try:
                width = float(width)
            except Exception:
                width = 0.0
            if width >= self._ANGLE_LIMIT:
                return {'message': 'Width limited to {} degrees.'.format(
                    self._ANGLE_LIMIT / 3600.)}
        if height is not None:
            try:
                height = float(height)
            except Exception:
                height = 0.0
            if height >= self._ANGLE_LIMIT:
                return {'message': 'Height limited to {} degrees.'.format(
                    self._ANGLE_LIMIT / 3600.)}

        if ename is None:
            if ra is not None and dec is not None:
                lcoo = coord(ra, dec, unit=(un.hourangle, un.deg))
                if (width is not None and height is not None and
                        width > 0.0 and height > 0.0):
                    idxcat = np.where((abs(
                        lcoo.ra - coo.ra) <= width * un.arcsecond) & (
                        abs(lcoo.dec - coo.dec) <= height * un.arcsecond))[0]
                elif width is not None and width > 0.0:
                    idxcat = np.where(abs(lcoo.ra - coo.ra) <=
                                      width * un.arcsecond)[0]
                elif height is not None and height > 0.0:
                    idxcat = np.where(abs(
                        lcoo.dec - coo.dec) <= height * un.arcsecond)[0]
                else:
                    if radius is None or radius == 0.0:
                        radius = 1.0
                    idxcat = np.where(lcoo.separation(coo) <=
                                      radius * un.arcsecond)[0]
                if len(idxcat):
                    ename = '+'.join([rdnames[i].replace('+', '$PLUS$')
                                      for i in idxcat])
                else:
                    return {'message':
                            'No objects found within specified search region.'}
            elif qname is None and aname is None:
                return catalogs.get(catalog_name, {})

        if fmt is not None and qname is None:
            return Response((
                'Error: "{}" format only supported if quantity '
                'is specified.').format(
                    fmt), mimetype='text/plain')
        # Events
        event_names = [] if ename is None else ename.split('+')
        # Check for + in names
        nevent_names = []
        joined = False
        for ni, name in enumerate(event_names):
            if joined:
                joined = False
                continue
            if ni < len(event_names) - 1:
                jname = '+'.join(event_names[ni:ni + 2])
                if jname.lower().replace(' ', '') in aliases:
                    nevent_names.append(jname)
                    joined = True
                    continue
            nevent_names.append(name)
        event_names = nevent_names

        event_names = [x.replace('$PLUS$', '+') for x in event_names]

        if not len(event_names):
            search_all = True
            event_names = all_events

        # Quantities
        quantity_names = [
        ] if qname is None else qname.split('+')

        # Attributes. Always append source.
        attribute_names = [
        ] if aname is None else aname.split('+')

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
                        return {'message': (
                            'Query too expensive, we suggest cloning the OAC '
                            'catalogs locally (see e.g. '
                            '"https://sne.space/download/").')}

        edict = OrderedDict()
        fcatalogs = OrderedDict()
        sources = OrderedDict()
        for event in event_names:
            my_cat, my_event = None, None
            alopts = aliases.get(event.lower().replace(' ', ''), [])
            for opt in alopts:
                if opt[0] == catalog_name:
                    my_cat, my_event, my_alias = tuple(opt)
            if not my_cat:
                for opt in alopts:
                    if opt[0] != catalog_name:
                        my_cat, my_event, my_alias = tuple(opt)
            if not my_cat:
                return {'message':
                        'Event "{}" not found in any catalog.'.format(event)}
            if full:
                fcatalogs.update(json.load(
                    open(os.path.join(
                        ac_path, catdict[my_cat], 'output', 'json',
                        get_filename(my_event)), 'r'),
                    object_pairs_hook=OrderedDict))
                sources[my_event] = [
                    x.get('bibcode', x.get('arxivid', x.get('name')))
                    for x in fcatalogs[my_event].get('sources')]
            if qname is None:
                if full:
                    edict[event] = fcatalogs.get(my_event, {})
                else:
                    edict[event] = catalogs.get(my_cat, {}).get(my_event, {})
            else:
                # Check if user passed quantity or attribute names to filter
                # by.
                qdict = OrderedDict()
                for quantity in quantity_names:
                    if full:
                        my_event_dict = fcatalogs.get(
                            my_event, {})
                    else:
                        my_event_dict = catalogs.get(my_cat, {}).get(
                            my_event, {})
                    my_quantity = my_event_dict.get(quantity, {})
                    closest_locs = []
                    if closest is not None:
                        closest_locs = list(sorted(list(set([
                            np.argmin([abs(np.mean([
                                float(y) for y in listify(x.get(i))]) - float(
                                    includes[i])) for x in my_quantity])
                            for i in includes if len(my_quantity) and
                            is_number(includes[i]) and
                            all([is_number(x.get(i))
                                 for x in my_quantity])]))))

                    if aname is None:
                        if not len(includes) or all([
                            (i in my_event_dict) if (
                                includes.get(i) == '') else (
                                includes.get(i).lower() in [
                                    v.get('value', '').lower() for v in
                                    my_event_dict.get(
                                        i, [])]) for i in includes]):
                            qdict[quantity] = [x for xi, x in enumerate(
                                my_quantity) if not len(
                                    closest_locs) or xi in closest_locs]

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

                    if not search_all and not qdict[quantity]:
                        use_full = True
                        break
                if not full and use_full:
                    break
                if qdict:
                    edict[event] = qdict

        if not full and use_full:
            return self.retrieve(
                catalog_name, ename, qname, aname, True)

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
                [','.join(sources[[int(y) - 1 for y in x.get(
                    a, '').split(',')]])
                 if a == 'source' else x.get(a, '') for a in anames]
                for xi, x in enumerate(quantity) if any(
                    [x.get(a) is not None for a in anames]) and (
                    (len(closest_locs) and xi in closest_locs) or
                    all([(i in x) if (includes.get(i) == '') else (
                        includes.get(i).lower() == x.get(i).lower())
                        for i in includes])) and
                not any([(e in x) if (excludes.get(e) == '') else (
                    excludes.get(e) == x.get(e)) for e in excludes])]
        else:
            attributes = [
                [','.join(sources[[int(y) - 1 for y in x.get(
                    a, '').split(',')]])
                 if a == 'source' else x.get(a, '') for a in anames]
                for xi, x in enumerate(quantity) if all(
                    [x.get(a) is not None for a in anames]) and (
                    (len(closest_locs) and xi in closest_locs) or
                    all([(i in x) if (includes.get(i) == '') else (
                        includes.get(i).lower() == x.get(i).lower())
                        for i in includes])) and
                not any([(e in x) if (excludes.get(e) == '') else (
                    excludes.get(e) == x.get(e)) for e in excludes])]

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
            if not len(anames) and len(qnames):
                cax = 'a'
            elif len(qnames) > 1:
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
            colheaders = list(anames if anames else qnames)
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
                if not anames:
                    outarr = [i for s in [
                        [[enames[ei]] + [','.join([v.get('value', '') for v in edict[e][q]])
                            for q in edict[e]]]
                        for ei, e in enumerate(edict)] for i in s]
                else:
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
all_events = []
for cat in catdict:
    for event in catalogs[cat]:
        all_events.append(event)
        levent = catalogs[cat].get(event, {})
        laliases = levent.get('alias', [])
        laliases = list(set([event] + [x['value'] for x in laliases]))
        for alias in laliases:
            aliases.setdefault(alias.lower().replace(' ', ''),
                               []).append([cat, event, alias])
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

all_events = list(sorted(set(all_events)))
coo = coord(ras, decs, unit=(un.hourangle, un.deg))

logger.info('Launching API...')
# app.run()
