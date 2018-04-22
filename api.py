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
from flask import Flask, Response, request
from six import string_types
from werkzeug.contrib.fixers import ProxyFix

from flask_compress import Compress
from flask_restful import Api, Resource

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
Compress(app)
api = Api(app)

catdict = OrderedDict((
    ('sne', 'supernovae'),
    ('tde', 'tidaldisruptions'),
    ('kilonova', 'kilonovae'),
    ('faststars', 'faststars')
))

catalogs = OrderedDict()
catalog_keys = OrderedDict()
aliases = OrderedDict()
coo = None
rdnames = []

ac_path = os.path.join('/root', 'astrocats', 'astrocats')

raregex = re.compile("^[0-9]{1,2}:[0-9]{2}(:?[0-9]{2}\.?([0-9]+)?)?$")
decregex = re.compile("^[+-]?[0-9]{1,2}:[0-9]{2}(:?[0-9]{2}\.?([0-9]+)?)?$")

logger = logging.getLogger('gunicorn.error')
logger.setLevel(logging.INFO)

messages = json.load(open('messages.json', 'r'))

dsv_fmts = ['csv', 'tsv']


def msg(name, reps=[], fmt=None):
    """Construct a response from the message dictinoary."""
    msg_txt = messages.get(
        name, messages.get('no_message', '')).format(
            *listify(reps))
    return (msg_txt if fmt in dsv_fmts else {'message': msg_txt})


def replace_multiple(y, xs, rep=''):
    """Match multiple strings to replace in sequence."""
    for x in xs:
        y = y.replace(x, rep)
    return y


def valf(x):
    """Return the `value` attribute of a quantity, if it exists."""
    return (x.get('value', '') if isinstance(x, dict) else x)


def commify(x):
    """Convert list of strings into a comma-delimited list."""
    lx = listify(x)
    lx = ('"' + ",".join(lx) + '"') if len(lx) > 1 else x
    return lx


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
    return (isinstance(x, list) and not isinstance(x, string_types))


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


class Catalogs(Resource):
    """Return all catalogs."""

    def get(self, catalog_name):
        """Get result."""
        return catalogs


class Catalog(Resource):
    """Return event info."""

    _ANGLE_LIMIT = 36000.0
    _EXPENSIVE = {
        'spectra': ['data']
    }
    _EXPENSIVE_LIMIT = 100
    _NO_CSV = []
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
        'item',
        'full',
        'download',
        'sortby',
        'event',
        'quantity',
        'attribute'
    ])
    _CASE_SENSITIVE_ATTR = set([
        'band'
    ])
    _ALWAYS_FULL = set([
        'source'
    ])

    def post(self, *args, **kwargs):
        """Handle POST request."""
        result = self.get(*args, **kwargs)
        return result, 200

    def get(self, catalog_name, event_name=None, quantity_name=None,
            attribute_name=None):
        """Get result."""
        logger.info('Query from {}: {} -- {}/{}/{} -- User Agent: {}'.format(
            request.remote_addr, catalog_name, event_name, quantity_name,
            attribute_name, request.headers.get('User-Agent', '?')))

        req_vals = request.get_json()

        if not req_vals:
            req_vals = request.values

        logger.info('Arguments: ' + json.dumps(req_vals))
        start = timer()
        result = self.retrieve(catalog_name, event_name,
                               quantity_name, attribute_name, False)
        end = timer()
        logger.info('Time to perform query: {}s'.format(end - start))
        if isinstance(result, Response):
            logger.info('Query successful!')
        elif 'message' in result:
            logger.info('Query unsuccessful, message: {}'.format(
                result['message']))
        elif not result:
            logger.info('Query unsuccessful, no results returned.')
        else:
            logger.info('Query successful!')

        if req_vals and 'download' in req_vals:
            ext = req_vals.get('format')
            ext = '.' + ext.lower() if ext is not None else '.json'
            if not isinstance(result, Response):
                result = Response(result, mimetype='text/plain')
            result.headers['Content-Disposition'] = (
                'attachment; filename=' + ext)

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

        if ename is None:
            return msg('no_root_data')

        # Options
        if not use_full:
            rfull = req_vals.get('full')
            if rfull is not None:
                return self.retrieve(
                    catalog_name, event_name=ename,
                    quantity_name=qname, attribute_name=aname,
                    full=True)

        fmt = req_vals.get('format')
        fmt = fmt.lower() if fmt is not None else fmt
        fmt = None if fmt == 'json' else fmt

        ra = req_vals.get('ra')
        dec = req_vals.get('dec')
        radius = req_vals.get('radius')
        width = req_vals.get('width')
        height = req_vals.get('height')
        complete = req_vals.get('complete')
        first = req_vals.get('first')
        closest = req_vals.get('closest')
        sortby = req_vals.get('sortby')

        sortby = sortby.lower() if sortby is not None else sortby

        include_keys = list(
            sorted(set(req_vals.keys()) - self._SPECIAL_ATTR))
        includes = OrderedDict()
        iincludes = OrderedDict()
        for key in include_keys:
            val = req_vals.get(key)
            if not is_number(val):
                val = '^' + val + '$'
            includes[key] = re.compile(val)
            iincludes[key] = re.compile(val, re.IGNORECASE)

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
                return msg('radius_limited', self._ANGLE_LIMIT / 3600.)
        if width is not None:
            try:
                width = float(width)
            except Exception:
                width = 0.0
            if width >= self._ANGLE_LIMIT:
                return msg('width_limited', self._ANGLE_LIMIT / 3600.)
        if height is not None:
            try:
                height = float(height)
            except Exception:
                height = 0.0
            if height >= self._ANGLE_LIMIT:
                return msg('height_limited', self._ANGLE_LIMIT / 3600.)

        if ename and ename.lower() in ['catalog', 'all']:
            if ra is not None and dec is not None:
                try:
                    ldec = str(dec).lower().strip(' .')
                    if is_number(ldec) or decregex.match(ldec):
                        sra = str(ra)
                        lra = sra.lower().replace('h', '').strip(' .')
                        if raregex.match(lra) or (is_number(lra) and 'h' in sra):
                            lcoo = coord(lra, ldec, unit=(un.hourangle, un.deg))
                        elif is_number(lra):
                            lcoo = coord(lra, ldec, unit=(un.deg, un.deg))
                        else:
                            raise Exception
                except Exception:
                    return msg('bad_coordinates')
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
                    ename_arr = [rdnames[i].replace('+', '$PLUS$')
                                 for i in idxcat]
                else:
                    return msg('no_objects')
            elif catalog_name in catalogs:
                ename_arr = [i.replace('+', '$PLUS$')
                             for i in catalogs[catalog_name]]
            else:
                ename_arr = [
                    a for b in [
                        [i.replace('+', '$PLUS$')
                         for i in catalogs[cat]] for cat in catalogs
                    ] for a in b
                ]
                search_all = True

            ename = '+'.join(list(sorted(set(ename_arr))))

        if qname is None:
            # Short circuit to full if keyword is present.
            if full:
                return self.retrieve(
                    catalog_name, event_name=ename, full=True)
            search_all = True
            if catalog_name not in catdict:
                qname = '+'.join(list(set(sorted([
                    a for b in [catalog_keys[x]
                                for x in catalog_keys] for a in b]))))
            else:
                qname = '+'.join(
                    list(sorted(set(catalog_keys[catalog_name]))))

        # if fmt is not None and qname is None:
        #    return Response((
        #        'Error: \'{}\' format only supported if quantity '
        #        'is specified.').format(
        #            fmt), mimetype='text/plain')

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
            return msg('max_events', self._FULL_LIMIT)

        if fmt is not None and any([n in attribute_names
                                    for n in self._NO_CSV]):
            return msg('no_delimited')

        if len(event_names) > self._EXPENSIVE_LIMIT:
            for quantity in quantity_names:
                for exp in self._EXPENSIVE:
                    if any([e in attribute_names for e in self._EXPENSIVE]):
                        return msg('too_expensive')

        edict = OrderedDict()
        fcatalogs = OrderedDict()
        sources = OrderedDict()
        new_event_names = []
        for event in event_names:
            skip_entry = False
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
                return msg('event_not_found', event)
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
                if full:
                    my_event_dict = fcatalogs.get(
                        my_event, {})
                else:
                    my_event_dict = catalogs.get(my_cat, {}).get(
                        my_event, {})

                if aname is None:
                    for incl in includes:
                        incll = incl.lower()
                        if incll not in my_event_dict or (
                            iincludes[incl].pattern != '' and not any([bool(iincludes[incl].match(x.get(
                                'value', '') if isinstance(x, dict) else x))
                                for x in my_event_dict.get(incll, [{}])])):
                            skip_entry = True
                            break

                if not skip_entry:
                    for quantity in quantity_names:
                        my_quantity = listify(my_event_dict.get(quantity, {}))
                        closest_locs = []
                        if closest is not None:
                            closest_locs = list(sorted(list(set([
                                np.argmin([abs(np.mean([
                                    float(y) for y in listify(
                                        x.get(i))]) - float(
                                            includes[
                                                i].pattern)) for x in my_quantity])
                                for i in includes if len(my_quantity) and
                                is_number(includes[i].pattern) and
                                all([is_number(x.get(i, ''))
                                     for x in my_quantity])]))))

                        if aname is None and quantity in my_event_dict:
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
                                attribute_names, my_quantity,
                                complete=complete,
                                full=use_full, item=item,
                                includes=includes, excludes=excludes,
                                closest_locs=closest_locs,
                                sources=np.array(sources.get(my_event, [])))

                        if not search_all and not qdict.get(quantity):
                            use_full = True
                            break
                if not full and use_full:
                    new_event_names = event_names
                    break
                if qdict:
                    edict[event] = qdict

            if not (skip_entry and (full or search_all)):
                new_event_names.append(event)

        event_names = new_event_names
        ename = '+'.join([i.replace('+', '$PLUS$')
                          for i in event_names])

        if not full and use_full:
            return self.retrieve(
                catalog_name, event_name=ename, quantity_name=qname,
                attribute_name=aname, full=True)

        if fmt is not None:
            return self.get_event_dsv(
                edict, event_names, quantity_names, attribute_names, fmt,
                sortby)

        return edict

    def get_attributes(
        self, anames, quantity, complete=None, full=False, item=None,
            includes={}, excludes={}, closest_locs=[], sources=[]):
        """Return array of attributes."""
        if complete is None:
            attributes = [
                ([','.join(sources[[int(y) - 1 for y in x.get(
                    a, '').split(',')]])
                  if a == 'source' else x.get(a, '') for a in anames]
                 if full else [x.get(a, '') for a in anames])
                for xi, x in enumerate(quantity) if any(
                    [x.get(a) is not None for a in anames]) and all(
                    [x.get(a) is not None for a in
                        self._ALWAYS_FULL.intersection(anames)]) and (
                    (len(closest_locs) and xi in closest_locs) or
                    all([(i in x) if (includes.get(i, re.compile('')).pattern == '') else (
                        includes.get(i, re.compile('')).match(commify(x.get(i, '')))
                        if i in self._CASE_SENSITIVE_ATTR else
                        iincludes.get(i, re.compile('')).match(commify(x.get(i, ''))))
                        for i in includes])) and
                not any([(e in x) if (excludes.get(e) == '') else (
                    excludes.get(e) == commify(x.get(e))) for e in excludes])]
        else:
            attributes = [
                ([','.join(sources[[int(y) - 1 for y in x.get(
                    a, '').split(',')]])
                  if a == 'source' else x.get(a, '') for a in anames]
                 if full else [x.get(a, '') for a in anames])
                for xi, x in enumerate(quantity) if all(
                    [x.get(a) is not None for a in anames]) and
                (not len(closest_locs) or xi in closest_locs) and (
                    (len(closest_locs) and xi in closest_locs) or
                    all([(i in x) if (includes.get(i, re.compile('').pattern) == '') else (
                        includes.get(i, re.compile('')).match(commify(x.get(i, '')))
                        if i in self._CASE_SENSITIVE_ATTR else
                        iincludes.get(i, re.compile('')).match(commify(x.get(i, ''))))
                        for i in includes])) and
                not any([(e in x) if (excludes.get(e) == '') else (
                    excludes.get(e) == commify(x.get(e))) for e in excludes])]

        if item is not None:
            try:
                attributes = [attributes[item]]
            except Exception:
                pass

        return attributes

    def get_event_dsv(
            self, edict, enames, qnames, anames, fmt='csv', sortby=None):
        """Get delimited table."""
        if fmt not in dsv_fmts:
            return msg('unknown_fmt')
        # Determine which to use as axes in CSV/TSV file.
        rax = None
        cax = None

        ename = enames[0] if enames else None
        qname = qnames[0] if qnames else None

        # Special case: Data array from a spectrum.
        if 'spectra' in qnames and 'data' in anames:
            if len(enames) != 1 or len(qnames) != 1 or len(anames) != 1:
                return msg('spectra_limits')
            attr = edict.get(ename, {}).get(qname, [])
            if len(attr) != 1 or len(attr[0]) != 1:
                return msg('one_spectra')
            data_str = ''
            for ri, row in enumerate(attr[0][0]):
                if ri == 0:
                    data_str += ','.join(['wavelength','flux'])
                    if len(row) > 2:
                        data_str += ',e_flux'
                    data_str += '\n'
                data_str += ','.join(row) + '\n'
            return Response(data_str, mimetype='text/plain')

        delim = ',' if fmt == 'csv' else '\t'

        if len(enames) > 0:
            rax = 'e'
            if not len(anames) and len(qnames):
                cax = 'a'
            elif len(qnames) > 1:
                cax = 'q'
                if len(anames) > 1:
                    return msg('fmt_unsupported', fmt.upper())
            elif len(anames):
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
                        [[enames[ei]] + ([
                            ','.join([valf(v) for v in listify(edict[e][q])])
                            for q in edict[e]] if len(edict[e]) else [])]
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
                outarr = [[delim.join([valf(y) for y in edict[ename][x]])]
                    for x in edict[ename]]
        elif rax == 'a':
            outarr = edict[ename][qname]
        else:
            outarr = listify(edict.get(ename, {}).get(qname, {}))

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

        # Sort the returned array.
        if sortby is not None:
            try:
                si = outarr[0].index(sortby)
            except Exception:
                return msg('cant_sort', reps=[sortby])
            outarr = [outarr[0]] + \
                list(sorted(outarr[1:], key=lambda x: x[si]))

        ret_arr = [
            delim.join([
                ('"' + delim.join(z) + '"') if is_list(
                    z) else z for z in y])
            for y in outarr]
        ret_str = '\n'.join(ret_arr)
        return Response(ret_str, mimetype='text/plain')


cn = '<string:catalog_name>'
en = '<string:event_name>'
qn = '<string:quantity_name>'
an = '<string:attribute_name>'

api.add_resource(Catalogs, '/'.join(['', cn, 'catalogs']))
api.add_resource(
    Catalog,
    '/'.join(['', cn]),
    '/'.join(['', cn]) + '/',
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
    catalogs[cat] = OrderedDict(sorted(dict(
        zip([x['name'] for x in catalogs[cat]], catalogs[cat])).items(),
        key=lambda s: (s[0].upper(), s[0])))
logger.info('Creating alias dictionary and position arrays...')
ras = []
decs = []
all_events = []
for cat in catdict:
    catalog_keys[cat] = set()
    for event in catalogs[cat]:
        all_events.append(event)
        catalog_keys[cat].update(list(catalogs[cat][event].keys()))
        levent = catalogs[cat].get(event, {})
        laliases = levent.get('alias', [])
        laliases = list(set([event.lower()] + [x['value'].lower() for x in
                                               laliases] + [
            replace_multiple(x['value'].lower(), ['sn', 'at'])
            for x in laliases if x['value'].lower().startswith((
                'sn', 'at'))] + [
            replace_multiple(x['value'].lower(), ['-', '–'])
            for x in laliases]))
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

all_events = list(sorted(set(all_events), key=lambda s: (s.upper(), s)))
coo = coord(ras, decs, unit=(un.hourangle, un.deg))

logger.info('Launching API...')
# app.run()
