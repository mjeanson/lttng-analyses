# The MIT License (MIT)
#
# Copyright (C) 2015 - Julien Desfossez <jdesfossez@efficios.com>
#               2015 - Antoine Busque <abusque@efficios.com>
#               2015 - Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import operator
from .command import Command
from ..core import memtop
from . import mi
from . import termgraph


class Memtop(Command):
    _DESC = """The memtop command."""
    _ANALYSIS_CLASS = memtop.Memtop
    _MI_TITLE = 'Top memory usage'
    _MI_DESCRIPTION = 'Per-TID and per-container top allocated/freed memory'
    _MI_TAGS = [mi.Tags.MEMORY, mi.Tags.TOP]
    _MI_TABLE_CLASS_ALLOCD = 'allocd'
    _MI_TABLE_CLASS_FREED = 'freed'
    _MI_TABLE_CLASS_PER_CONTAINER_ALLOCD = 'per-container-allocd'
    _MI_TABLE_CLASS_PER_CONTAINER_FREED = 'per-container-freed'
    _MI_TABLE_CLASS_TOTAL = 'total'
    _MI_TABLE_CLASS_SUMMARY = 'summary'
    _MI_TABLE_CLASSES = [
        (
            _MI_TABLE_CLASS_ALLOCD,
            'Per-TID top allocated memory', [
                ('process', 'Process', mi.Process),
                ('pages', 'Allocated pages', mi.Number, 'pages'),
            ]
        ),
        (
            _MI_TABLE_CLASS_FREED,
            'Per-TID top freed memory', [
                ('process', 'Process', mi.Process),
                ('pages', 'Freed pages', mi.Number, 'pages'),
            ]
        ),
        (
            _MI_TABLE_CLASS_PER_CONTAINER_ALLOCD,
            'Per-Container top allocated memory', [
                ('container', 'Container', mi.Container),
                ('pages', 'Allocated pages', mi.Number, 'pages'),
            ]
        ),
        (
            _MI_TABLE_CLASS_PER_CONTAINER_FREED,
            'Per-Container top freed memory', [
                ('container', 'Container', mi.Container),
                ('pages', 'Freed pages', mi.Number, 'pages'),
            ]
        ),
        (
            _MI_TABLE_CLASS_TOTAL,
            'Total allocated/freed memory', [
                ('allocd', 'Total allocated pages', mi.Number, 'pages'),
                ('freed', 'Total freed pages', mi.Number, 'pages'),
            ]
        ),
        (
            _MI_TABLE_CLASS_SUMMARY,
            'Memory usage - summary', [
                ('time_range', 'Time range', mi.TimeRange),
                ('allocd', 'Total allocated pages', mi.Number, 'pages'),
                ('freed', 'Total freed pages', mi.Number, 'pages'),
            ]
        ),
    ]

    def _analysis_tick(self, period_data, end_ns):
        if period_data is None:
            return

        begin_ns = period_data.period.begin_evt.timestamp
        allocd_table = self._get_per_tid_allocd_result_table(period_data,
                                                             begin_ns, end_ns)
        freed_table = self._get_per_tid_freed_result_table(period_data,
                                                           begin_ns, end_ns)
        per_container_allocd_table = self._get_per_container_allocd_result_table(period_data,
                                                             begin_ns, end_ns)
        per_container_freed_table = self._get_per_container_freed_result_table(period_data,
                                                           begin_ns, end_ns)
        total_table = self._get_total_result_table(period_data,
                                                   begin_ns, end_ns)

        if self._mi_mode:
            self._mi_append_result_table(allocd_table)
            self._mi_append_result_table(freed_table)
            self._mi_append_result_table(per_container_allocd_table)
            self._mi_append_result_table(per_container_freed_table)
            self._mi_append_result_table(total_table)
        else:
            self._print_date(begin_ns, end_ns)
            self._print_per_tid_allocd(allocd_table)
            self._print_per_tid_freed(freed_table)
            self._print_per_container_allocd(per_container_allocd_table)
            self._print_per_container_freed(per_container_freed_table)
            self._print_total(total_table)

    def _create_summary_result_tables(self):
        total_tables = self._mi_get_result_tables(self._MI_TABLE_CLASS_TOTAL)
        begin = total_tables[0].timerange.begin.value
        end = total_tables[-1].timerange.end.value
        summary_table = \
            self._mi_create_result_table(self._MI_TABLE_CLASS_SUMMARY,
                                         begin, end)

        for total_table in total_tables:
            total_allocd = total_table.rows[0].allocd
            total_freed = total_table.rows[0].freed
            summary_table.append_row(
                time_range=total_table.timerange,
                allocd=total_allocd,
                freed=total_freed,
            )

        self._mi_clear_result_tables()
        self._mi_append_result_table(summary_table)

    def _get_per_tid_attr_result_table(self, period_data, table_class, attr,
                                       begin_ns, end_ns):
        result_table = self._mi_create_result_table(table_class,
                                                    begin_ns, end_ns)
        count = 0

        for tid in sorted(period_data.tids.values(),
                          key=operator.attrgetter(attr),
                          reverse=True):
            result_table.append_row(
                process=mi.Process(tid.comm, tid=tid.tid),
                pages=mi.Number(getattr(tid, attr)),
            )
            count += 1

            if self._args.limit > 0 and count >= self._args.limit:
                break

        return result_table

    def _get_per_tid_allocd_result_table(self, period_data, begin_ns, end_ns):
        return self._get_per_tid_attr_result_table(period_data,
                                                   self._MI_TABLE_CLASS_ALLOCD,
                                                   'allocated_pages',
                                                   begin_ns, end_ns)

    def _get_per_tid_freed_result_table(self, period_data, begin_ns, end_ns):
        return self._get_per_tid_attr_result_table(period_data,
                                                   self._MI_TABLE_CLASS_FREED,
                                                   'freed_pages',
                                                   begin_ns, end_ns)

    def _get_per_container_attr_result_table(self, period_data, table_class, attr,
                                       begin_ns, end_ns):
        result_table = self._mi_create_result_table(table_class,
                                                    begin_ns, end_ns)
        count = 0

        for container in sorted(period_data.containers.values(),
                          key=operator.attrgetter('pid_ns'),
                          reverse=True):
            result_table.append_row(
                container=mi.Container(container.pid_ns, container.name, container.c_type),
                pages=mi.Number(getattr(container, attr)),
            )
            count += 1

            if self._args.limit > 0 and count >= self._args.limit:
                break

        return result_table

    def _get_per_container_allocd_result_table(self, period_data, begin_ns, end_ns):
        return self._get_per_container_attr_result_table(period_data,
                                                   self._MI_TABLE_CLASS_PER_CONTAINER_ALLOCD,
                                                   'allocated_pages',
                                                   begin_ns, end_ns)

    def _get_per_container_freed_result_table(self, period_data, begin_ns, end_ns):
        return self._get_per_container_attr_result_table(period_data,
                                                   self._MI_TABLE_CLASS_PER_CONTAINER_FREED,
                                                   'freed_pages',
                                                   begin_ns, end_ns)

    def _get_total_result_table(self, period_data, begin_ns, end_ns):
        result_table = self._mi_create_result_table(self._MI_TABLE_CLASS_TOTAL,
                                                    begin_ns, end_ns)
        alloc = 0
        freed = 0

        for tid in period_data.tids.values():
            alloc += tid.allocated_pages
            freed += tid.freed_pages

        result_table.append_row(
            allocd=mi.Number(alloc),
            freed=mi.Number(freed),
        )

        return result_table

    def _print_per_tid_result(self, result_table, title):
        graph = termgraph.BarGraph(
            title=title,
            unit='pages',
            get_value=lambda row: row.pages.value,
            get_label=lambda row: '%s (%d)' % (row.process.name,
                                               row.process.tid),
            label_header='Process',
            data=result_table.rows
        )

        graph.print_graph()

    def _print_per_tid_allocd(self, result_table):
        self._print_per_tid_result(result_table, 'Per-TID Memory Allocations')

    def _print_per_tid_freed(self, result_table):
        self._print_per_tid_result(result_table,
                                   'Per-TID Memory Deallocations')

    def _print_per_container_result(self, result_table, title):
        row_format = '  {:<45} {:<10}'
        label_header = row_format.format('Container', 'Type')

        def format_label(row):
            return row_format.format(
                '%s (%d)' % (row.container.name, row.container.pid_ns),
                row.container.c_type,
            )

        graph = termgraph.BarGraph(
            title=title,
            unit='pages',
            get_value=lambda row: row.pages.value,
            get_label=format_label,
            label_header=label_header,
            data=result_table.rows
        )

        graph.print_graph()

    def _print_per_container_allocd(self, result_table):
        self._print_per_container_result(result_table, 'Per-Container Memory Allocations')

    def _print_per_container_freed(self, result_table):
        self._print_per_container_result(result_table,
                                   'Per-Container Memory Deallocations')

    def _print_total(self, result_table):
        alloc = result_table.rows[0].allocd.value
        freed = result_table.rows[0].freed.value
        print('\nTotal memory usage:\n- %d pages allocated\n- %d pages freed' %
              (alloc, freed))

    def _add_arguments(self, ap):
        Command._add_proc_filter_args(ap)
        Command._add_top_args(ap)


def _run(mi_mode):
    memtopcmd = Memtop(mi_mode=mi_mode)
    memtopcmd.run()


# entry point (human)
def run():
    _run(mi_mode=False)


# entry point (MI)
def run_mi():
    _run(mi_mode=True)
