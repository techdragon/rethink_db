import rethinkdb as rdb

from nio.block.mixins import EnrichSignals
from nio.properties import StringProperty, Property

from .rethinkdb_base_block import RethinkDBBase


class RethinkDBDelete(EnrichSignals, RethinkDBBase):

    """a block for deleting one or more documents from a rethinkdb table"""

    table = StringProperty(title="Table to query", default='test',
                           allow_none=False)
    filter = Property(title='Filter by given fields',
                      default='{{ $.to_dict() }}',
                      allow_none=False)

    def _locked_process_signals(self, signals):
        notify_list = []
        for signal in signals:
            self.logger.debug('Delete is Processing signal: {}'.format(signal))
            # update incoming signals with results of the query
            delete_results = self.execute_with_retry(self._delete, signal)
            self.logger.debug("Delete results: {}".format(delete_results))
            out_sig = self.get_output_signal(delete_results, signal)
            notify_list.append(out_sig)

        self.notify_signals(notify_list)

    def _delete(self, signal):
        with rdb.connect(
                host=self.host(),
                port=self.port(),
                db=self.database_name(),
                timeout=self.connect_timeout().total_seconds()) as conn:

            # this will return the typical deleted, errors, unchanges, etc.
            # as well as changes. If the delete was successful, 'new_val' will
            # be none in changes.

            # Query table configuration to get primary key
            table_config = rdb.db(self.database_name()).table(self.table()).\
                config()
            primary_key = [table_config["primary_key"]]
            filter_condition = self.filter(signal)

            # Check if filter condition is only primary key, if so, use
            # .get rather than .filter for better performance
            if list(filter_condition.keys()) == primary_key:
                results = rdb.db(self.database_name()).table(self.table()). \
                    get(filter_condition).delete(return_changes=True). \
                    run(conn)
            else:
                results = rdb.db(self.database_name()).table(self.table()).\
                    filter(self.filter(signal)).delete(return_changes=True).\
                    run(conn)

        if results["deleted"] == 0:
            self.logger.debug("Unable to delete document for signal: {}"
                              .format(signal))

        self.logger.debug("Deleting using filter {} return results: {}"
                          .format(self.filter(signal), results))
        return results
