# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.api import model
from odoo.tools.sql import existing_tables
import pytz
from typing import Iterator, Mapping
from collections import abc
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta


from odoo import _


class GoogleEvent(abc.Set):
    """This helper class holds the values of a Google event.
    Inspired by Odoo recordset, one instance can be a single Google event or a
    (immutable) set of Google events.
    All usual set operations are supported (union, intersection, etc).

    A list of all attributes can be found in the API documentation.
    https://developers.google.com/calendar/v3/reference/events#resource

    :param iterable: iterable of GoogleCalendar instances or iterable of dictionnaries

    """

    def __init__(self, iterable=()):
        self._events = {}
        for item in iterable:
            if isinstance(item, self.__class__):
                self._events[item.id] = item._events[item.id]
            elif isinstance(item, Mapping):
                self._events[item.get('id')] = item
            else:
                raise ValueError("Only %s or iterable of dict are supported" % self.__class__.__name__)

    def __iter__(self) ->  Iterator['GoogleEvent']:
        return iter(GoogleEvent([vals]) for vals in self._events.values())

    def __contains__(self, google_event):
        return google_event.id in self._events

    def __len__(self):
        return len(self._events)

    def __bool__(self):
        return bool(self._events)

    def __getattr__(self, name):
        # ensure_one
        try:
            event, = self._events.keys()
        except ValueError:
            raise ValueError("Expected singleton: %s" % self)
        event_id = list(self._events.keys())[0]
        return self._events[event_id].get(name)

    def __repr__(self):
        return '%s%s' % (self.__class__.__name__, self.ids)

    @property
    def ids(self):
        return tuple(e.id for e in self)

    @property
    def rrule(self):
        if self.recurrence and 'RRULE:' in self.recurrence[0]:  # LUL TODO what if there are something else in the list?
            return self.recurrence[0][6:]  # skip "RRULE:" in the rrule string

    def odoo_id(self, env):
        self.odoo_ids(env)  # load ids
        return self._odoo_id

    def _meta_odoo_id(self, dbname):
        """Returns the Odoo id stored in the Google Event metadata.
        This id might not actually exists in the database.
        """
        properties = self.extendedProperties and self.extendedProperties.get('shared', {}) or {}
        o_id = properties.get('%s_odoo_id' % dbname)
        if o_id:
            return int(o_id)

    def odoo_ids(self, env):
        ids = tuple(e._odoo_id for e in self if e._odoo_id)
        if len(ids) == len(self):
            return ids
        found = self._load_odoo_ids_from_db(env)
        unsure = self - found
        if unsure:
            unsure._load_odoo_ids_from_metadata(env)

        return tuple(e._odoo_id for e in self)

    def _load_odoo_ids_from_metadata(self, env):
        model = self._get_model(env)
        unsure_odoo_ids = tuple(e._meta_odoo_id(env.cr.dbname) for e in self)
        odoo_events = model.browse(_id for _id in unsure_odoo_ids if _id)

        # Extended properties are copied when splitting a recurrence Google side.
        # Hence, we may have two Google recurrences linked to the same Odoo id.
        # Therefore, we only consider Odoo records without google id when trying
        # to match events.
        o_ids = odoo_events.exists().filtered(lambda e: not e.google_id).ids
        for e in self:
            odoo_id = e._meta_odoo_id(env.cr.dbname)
            if odoo_id in o_ids:
                e._events[e.id]['_odoo_id'] = odoo_id

    def _load_odoo_ids_from_db(self, env):
        model = self._get_model(env)
        odoo_events = model.with_context(active_test=False)._from_google_ids(self.ids)
        mapping = {e.google_id: e.id for e in odoo_events}  # {google_id: odoo_id}
        existing_google_ids = odoo_events.mapped('google_id')
        for e in self:
            odoo_id = mapping.get(e.id)
            if odoo_id:
                e._events[e.id]['_odoo_id'] = odoo_id
        return self.filter(lambda e: e.id in existing_google_ids)


    def owner(self, env):
        # Owner/organizer could be desynchronised between Google and Odoo.
        # Let userA, userB be two new users (never synced to Google before).
        # UserA creates an event in Odoo (he is the owner) but userB syncs first.
        # There is no way to insert the event into userA's calendar since we don't have
        # any authentication access. The event is therefore inserted into userB's calendar
        # (he is the orginizer in Google). The "real" owner (in Odoo) is stored as an
        # extended property. There is currently no support to "transfert" ownership when
        # userA syncs his calendar the first time.
        real_owner_id = self.extendedProperties and self.extendedProperties.get('shared', {}).get('%s_owner_id' % env.cr.dbname)
        real_owner = real_owner_id and env['res.users'].browse(int(real_owner_id))
        if real_owner_id and real_owner.exists():
            return real_owner
        elif self.organizer and self.organizer.get('self'):
            return env.user
        elif self.organizer and self.organizer.get('email'):
            # In Google: 1 email = 1 user; but in Odoo several users might have the same email :/
            return env['res.users'].search([('email', '=', self.organizer.get('email'))], limit=1)
        else:
            return env['res.users']

    def filter(self, func) -> 'GoogleEvent':
        return GoogleEvent(e for e in self if func(e))

    def is_recurrence(self):
        return bool(self.recurrence)

    def is_recurrent(self):
        return bool(self.recurringEventId or self.is_recurrence())

    def is_cancelled(self):
        return self.status == 'cancelled'

    def is_recurrence_outlier(self):
        return bool(self.originalStartTime)

    def cancelled(self):
        return self.filter(lambda e: e.status == 'cancelled')

    def exists(self, env) -> 'GoogleEvent':
        recurrences = self.filter(GoogleEvent.is_recurrence)
        events = self - recurrences
        recurrences.odoo_ids(env)
        events.odoo_ids(env)

        return self.filter(lambda e: e._odoo_id)

    def _get_model(self, env):
        if all([e.is_recurrence() for e in self]):
            return env['calendar.recurrence']
        elif all([not e.is_recurrence() for e in self]):
            return env['calendar.event']
        raise TypeError("Mixing Google events and Google recurrences")