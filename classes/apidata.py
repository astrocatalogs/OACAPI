"""Definitions for `ApiData` class."""
import os
from collections import OrderedDict


class ApiData(object):
    """Object to store data for the OACAPI."""

    _CATS = OrderedDict((
        ('sne', ['supernovae', 'catalog.min.json', 'sne-2015-2019']),
        ('tde', ['tidaldisruptions', 'catalog.min.json', 'tde-2015-2019']),
        ('kilonova', ['kilonovae', 'catalog.min.json', 'kne-2000-2029']),
        ('faststars', ['faststars', 'catalog.min.json', 'faststars-output']),
        ('sne-graveyard', ['supernovae', 'bones.min.json', 'sne-boneyard']),
        ('tde-graveyard', [
            'tidaldisruptions', 'bones.min.json', 'tde-boneyard']),
        ('kilonova-graveyard', [
            'kilonovae', 'bones.min.json', 'kne-boneyard']),
        ('faststars-graveyard', [
            'faststars', 'bones.min.json', 'faststars-boneyard'])
    ))

    _AC_PATH = os.path.join('/root', 'astrocats', 'astrocats')

    def __init__(self):
        """Initialize."""
        self._coo = None
        self._catalogs = OrderedDict()
        self._cat_keys = OrderedDict()
        self._aliases = OrderedDict()
        self._all_aliases = set()
        self._extras = OrderedDict()
        self._ras = []
        self._decs = []
        self._all_events = []
        self._rdnames = []
