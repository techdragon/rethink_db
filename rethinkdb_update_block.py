from nio.signal.base import Signal
from nio.properties import (StringProperty, ListProperty, PropertyHolder,
                            Property)
from nio.util.discovery import discoverable
from .rethinkdb_base_block import RethinkDBBase


class MatchItem(PropertyHolder):
    key = Property(title='Match key')


@discoverable
class RethinkDBUpdate(RethinkDBBase):

    """a block for updating info in a RethinkDB table"""

    table = StringProperty(title="Table to update", default='test',
                           allow_none=False)
    filters = ListProperty(MatchItem, title='Match the following document keys',
                           default=[])

    def __init__(self):
        super().__init__()
        # current table being updated
        self._table = None

    def configure(self, context):
        super().configure(context)
        self._set_table()

    def process_signals(self, signals):
        for signal in signals:
            self.logger.debug('Update is Processing signal: {}'.format(signal))
            self.update_table(signal)
        self.notify_signals(signals)

    def update_table(self, signal):
        """filter by given fields and update the correct document in the
        table
        """
        data = signal.to_dict()
        filter_dict = {}

        for key in (filter.key() for filter in self.filters()):
            try:
                filter_dict.update({key: data[key]})
            except:
                self.logger.exception('Filter "{}" was not found in the '
                                      'incoming signal. Aborting update.'
                                      .format(key))
                return

        self.logger.debug("Updating using filters: {}".format(filter_dict))
        field_filter = self._table.filter(filter_dict)

        # rethink does not allow updating of id.
        if 'id' in data:
            data.pop('id')

        result = field_filter.update(data).run(self._connection)

        self.logger.debug("Sent update request, result: {}".format(result))

        if result['errors'] > 0:
            # only first error is collected
            self.logger.error('Error updating table: {}'
                              .format(result['first_error']))
        else:
            # if no errors, there should only be integer result fields, which
            # should sum to greater than 0 if anything was replaced, updated,
            # etc.
            if not sum(result.values()):
                # if 0, it did nothing, which means that it found no matches
                # with the given filters.
                self.logger.debug('(no document fields matching given filters)')

        self.notify_signals(Signal(result))

    def _set_table(self):
        """set _table to a table object tied to the current db"""
        self._table = self._db.table(self.table())
