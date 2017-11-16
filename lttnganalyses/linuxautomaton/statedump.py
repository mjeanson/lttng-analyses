# The MIT License (MIT)
#
# Copyright (C) 2015 - Julien Desfossez <jdesfossez@efficios.com>
#               2015 - Antoine Busque <abusque@efficios.com>
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

import os
from . import sp, sv


class StatedumpStateProvider(sp.StateProvider):
    def __init__(self, state):
        cbs = {
            'lttng_statedump_process_state':
            self._process_lttng_statedump_process_state,
            'lttng_statedump_process_pid_ns':
            self._process_lttng_statedump_process_pid_ns,
            'lttng_statedump_file_descriptor':
            self._process_lttng_statedump_file_descriptor,
            'lttng_statedump_block_device':
            self._process_lttng_statedump_block_device,
            'lttng_statedump_container':
            self._process_lttng_statedump_container,
            'ust_container_statedump:lttng_statedump_container':
            self._process_lttng_statedump_container,
        }

        super().__init__(state, cbs)

    def _process_lttng_statedump_block_device(self, event):
        dev = event['dev']
        diskname = event['diskname']

        if dev not in self._state.disks:
            self._state.disks[dev] = sv.Disk(dev, diskname=diskname)
        elif self._state.disks[dev].diskname is None:
            self._state.disks[dev].diskname = diskname
        self._state.send_notification_cb('lttng_statedump_block_device',
                                         dev=dev, diskname=diskname)

    def _process_lttng_statedump_process_state(self, event):
        tid = event['tid']
        pid = event['pid']
        name = event['name']
        # prio is not in the payload for LTTng-modules < 2.8. Using
        # get() will set it to None if the key is not found
        prio = event.get('prio')

        if tid not in self._state.tids:
            self._state.tids[tid] = sv.Process(tid=tid)

        proc = self._state.tids[tid]
        # Even if the process got created earlier, some info might be
        # missing, add it now.
        proc.pid = pid
        proc.comm = name
        # However don't override the prio value if we already got the
        # information from sched_* events.
        if proc.prio is None:
            proc.prio = prio

        if pid != tid:
            # create the parent
            if pid not in self._state.tids:
                # FIXME: why is the parent's name set to that of the
                # child? does that make sense?

                # tid == pid for the parent process
                self._state.tids[pid] = sv.Process(tid=pid, pid=pid, comm=name)

            parent = self._state.tids[pid]
            # If the thread had opened FDs, they need to be assigned
            # to the parent.
            StatedumpStateProvider._assign_fds_to_parent(proc, parent)
            self._state.send_notification_cb('create_parent_proc',
                                             proc=proc,
                                             parent_proc=parent)

    def _process_lttng_statedump_process_pid_ns(self, event):
        tid = event['tid']
        vtid = event['vtid']
        vpid = event['vpid']

        ns_level = event['ns_level']
        ns_inum = event['ns_inum']

        # Add the highest level vpid and ns_inum to the Process object
        if tid in self._state.tids:
            if self._state.tids[tid].pid_ns_level > ns_level:
                self._state.tids[tid].pid_ns_level = ns_level
                self._state.tids[tid].pid_ns = ns_inum
                self._state.tids[tid].vtid = vtid
                self._state.tids[tid].vpid = vpid

        # The namespace of tid 1 will always be the root namespace
        if tid == 1:
            if ns_inum not in self._state.containers:
                self._state.containers[ns_inum] = sv.Container(ns_inum,
                                                              "host",
                                                              "[HOST]")
                self._state.send_notification_cb('create_container',
                                                 pid_ns=ns_inum,
                                                 container_type="host",
                                                 container_name="[HOST]")

    def _process_lttng_statedump_file_descriptor(self, event):
        pid = event['pid']
        fd = event['fd']
        filename = event['filename']
        cloexec = event['flags'] & os.O_CLOEXEC == os.O_CLOEXEC

        if pid not in self._state.tids:
            self._state.tids[pid] = sv.Process(tid=pid, pid=pid)

        proc = self._state.tids[pid]

        if fd not in proc.fds:
            proc.fds[fd] = sv.FD(fd, filename, sv.FDType.unknown, cloexec)
            self._state.send_notification_cb('create_fd',
                                             fd=fd,
                                             parent_proc=proc,
                                             timestamp=event.timestamp,
                                             cpu_id=event['cpu_id'])
        else:
            # just fix the filename
            proc.fds[fd].filename = filename
            self._state.send_notification_cb('update_fd',
                                             fd=fd,
                                             parent_proc=proc,
                                             timestamp=event.timestamp,
                                             cpu_id=event['cpu_id'])

    def _process_lttng_statedump_container(self, event):
        container_type = event['container_type']
        container_name = event['container_name']
        pid_ns = event['pid_ns']

        if pid_ns not in self._state.containers:
            self._state.containers[pid_ns] = sv.Container(pid_ns,
                                                          container_type,
                                                          container_name)
            self._state.send_notification_cb('create_container',
                                             pid_ns=pid_ns,
                                             container_type=container_type,
                                             container_name=container_name)

    @staticmethod
    def _assign_fds_to_parent(proc, parent):
        if proc.fds:
            toremove = []
            for fd in proc.fds:
                if fd not in parent.fds:
                    parent.fds[fd] = proc.fds[fd]
                else:
                    # best effort to fix the filename
                    if not parent.fds[fd].filename:
                        parent.fds[fd].filename = proc.fds[fd].filename
                toremove.append(fd)
            for fd in toremove:
                del proc.fds[fd]
