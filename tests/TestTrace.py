#!/usr/bin/env python3

import sys
import os
import shutil
import tempfile
import difflib
import subprocess
from babeltrace import CTFWriter, CTFStringEncoding


class TestTrace():
    def __init__(self, delete_trace=True):
        self.delete_trace = delete_trace
        self.trace_root = tempfile.mkdtemp()
        self.trace_path = os.path.join(self.trace_root, "kernel")
        self.create_writer()
        self.create_stream_class()
        self.define_base_types()
        self.define_events()
        self.create_stream()

    def __del__(self):
        if self.delete_trace:
            self.rm_trace()

    def get_trace_root(self):
        return self.trace_root

    def rm_trace(self):
        shutil.rmtree(self.trace_root)

    def flush(self):
        self.writer.flush_metadata()
        self.stream.flush()

    def create_writer(self):
        self.clock = CTFWriter.Clock("A_clock")
        self.clock.description = "Simple clock"
        self.writer = CTFWriter.Writer(self.trace_path)
        self.writer.add_clock(self.clock)
        self.writer.add_environment_field("Python_version",
                                          str(sys.version_info))
        self.writer.add_environment_field("tracer_major", 2)
        self.writer.add_environment_field("tracer_minor", 8)
        self.writer.add_environment_field("tracer_patchlevel", 0)

    def create_stream_class(self):
        self.stream_class = CTFWriter.StreamClass("test_stream")
        self.stream_class.clock = self.clock

    def define_base_types(self):
        self.char8_type = CTFWriter.IntegerFieldDeclaration(8)
        self.char8_type.signed = True
        self.char8_type.encoding = CTFStringEncoding.UTF8
        self.char8_type.alignment = 8

        self.int32_type = CTFWriter.IntegerFieldDeclaration(32)
        self.int32_type.signed = True
        self.int32_type.alignment = 8

        self.uint32_type = CTFWriter.IntegerFieldDeclaration(32)
        self.uint32_type.signed = False
        self.uint32_type.alignment = 8

        self.int64_type = CTFWriter.IntegerFieldDeclaration(64)
        self.int64_type.signed = True
        self.int64_type.alignment = 8

        self.array_type = CTFWriter.ArrayFieldDeclaration(self.char8_type, 16)

        self.string_type = CTFWriter.StringFieldDeclaration()

    def define_sched_switch(self):
        self.sched_switch = CTFWriter.EventClass("sched_switch")
        self.sched_switch.add_field(self.array_type, "_prev_comm")
        self.sched_switch.add_field(self.int32_type, "_prev_tid")
        self.sched_switch.add_field(self.int32_type, "_prev_prio")
        self.sched_switch.add_field(self.int64_type, "_prev_state")
        self.sched_switch.add_field(self.array_type, "_next_comm")
        self.sched_switch.add_field(self.int32_type, "_next_tid")
        self.sched_switch.add_field(self.int32_type, "_next_prio")
        self.sched_switch.add_field(self.uint32_type, "_cpu_id")
        self.stream_class.add_event_class(self.sched_switch)

    def define_softirq_raise(self):
        self.softirq_raise = CTFWriter.EventClass("softirq_raise")
        self.softirq_raise.add_field(self.uint32_type, "_vec")
        self.softirq_raise.add_field(self.uint32_type, "_cpu_id")
        self.stream_class.add_event_class(self.softirq_raise)

    def define_softirq_entry(self):
        self.softirq_entry = CTFWriter.EventClass("softirq_entry")
        self.softirq_entry.add_field(self.uint32_type, "_vec")
        self.softirq_entry.add_field(self.uint32_type, "_cpu_id")
        self.stream_class.add_event_class(self.softirq_entry)

    def define_softirq_exit(self):
        self.softirq_exit = CTFWriter.EventClass("softirq_exit")
        self.softirq_exit.add_field(self.uint32_type, "_vec")
        self.softirq_exit.add_field(self.uint32_type, "_cpu_id")
        self.stream_class.add_event_class(self.softirq_exit)

    def define_irq_handler_entry(self):
        self.irq_handler_entry = CTFWriter.EventClass("irq_handler_entry")
        self.irq_handler_entry.add_field(self.int32_type, "_irq")
        self.irq_handler_entry.add_field(self.string_type, "_name")
        self.irq_handler_entry.add_field(self.uint32_type, "_cpu_id")
        self.stream_class.add_event_class(self.irq_handler_entry)

    def define_irq_handler_exit(self):
        self.irq_handler_exit = CTFWriter.EventClass("irq_handler_exit")
        self.irq_handler_exit.add_field(self.int32_type, "_irq")
        self.irq_handler_exit.add_field(self.int32_type, "_ret")
        self.irq_handler_exit.add_field(self.uint32_type, "_cpu_id")
        self.stream_class.add_event_class(self.irq_handler_exit)

    def define_events(self):
        self.define_sched_switch()
        self.define_softirq_raise()
        self.define_softirq_entry()
        self.define_softirq_exit()
        self.define_irq_handler_entry()
        self.define_irq_handler_exit()

    def create_stream(self):
        self.stream = self.writer.create_stream(self.stream_class)

    def set_char_array(self, event, string):
        if len(string) > 16:
            string = string[0:16]
        else:
            string = "%s" % (string + "\0" * (16 - len(string)))

        for i in range(len(string)):
            a = event.field(i)
            a.value = ord(string[i])

    def set_int(self, event, value):
        event.value = value

    def set_string(self, event, value):
        event.value = value

    def write_softirq_raise(self, time_ms, cpu_id, vec):
        event = CTFWriter.Event(self.softirq_raise)
        self.clock.time = time_ms * 1000000
        self.set_int(event.payload("_cpu_id"), cpu_id)
        self.set_int(event.payload("_vec"), vec)
        self.stream.append_event(event)
        self.stream.flush()

    def write_softirq_entry(self, time_ms, cpu_id, vec):
        event = CTFWriter.Event(self.softirq_entry)
        self.clock.time = time_ms * 1000000
        self.set_int(event.payload("_cpu_id"), cpu_id)
        self.set_int(event.payload("_vec"), vec)
        self.stream.append_event(event)
        self.stream.flush()

    def write_softirq_exit(self, time_ms, cpu_id, vec):
        event = CTFWriter.Event(self.softirq_exit)
        self.clock.time = time_ms * 1000000
        self.set_int(event.payload("_cpu_id"), cpu_id)
        self.set_int(event.payload("_vec"), vec)
        self.stream.append_event(event)
        self.stream.flush()

    def write_irq_handler_entry(self, time_ms, cpu_id, irq, name):
        event = CTFWriter.Event(self.irq_handler_entry)
        self.clock.time = time_ms * 1000000
        self.set_int(event.payload("_cpu_id"), cpu_id)
        self.set_int(event.payload("_irq"), irq)
        self.set_string(event.payload("_name"), name)
        self.stream.append_event(event)
        self.stream.flush()

    def write_irq_handler_exit(self, time_ms, cpu_id, irq, ret):
        event = CTFWriter.Event(self.irq_handler_exit)
        self.clock.time = time_ms * 1000000
        self.set_int(event.payload("_cpu_id"), cpu_id)
        self.set_int(event.payload("_irq"), irq)
        self.set_int(event.payload("_ret"), ret)
        self.stream.append_event(event)
        self.stream.flush()

    def write_sched_switch(self, time_ms, cpu_id, prev_comm, prev_tid,
                           next_comm, next_tid, prev_prio=20, prev_state=1,
                           next_prio=20):
        event = CTFWriter.Event(self.sched_switch)
        self.clock.time = time_ms * 1000000
        self.set_char_array(event.payload("_prev_comm"), prev_comm)
        self.set_int(event.payload("_prev_tid"), prev_tid)
        self.set_int(event.payload("_prev_prio"), prev_prio)
        self.set_int(event.payload("_prev_state"), prev_state)
        self.set_char_array(event.payload("_next_comm"), next_comm)
        self.set_int(event.payload("_next_tid"), next_tid)
        self.set_int(event.payload("_next_prio"), next_prio)
        self.set_int(event.payload("_cpu_id"), cpu_id)
        self.stream.append_event(event)
        self.stream.flush()

    def sched_switch_50pc(self, start_time_ms, end_time_ms, cpu_id, period,
                          comm1, tid1, comm2, tid2):
        current = start_time_ms
        while current < end_time_ms:
            self.write_sched_switch(current, cpu_id, comm1, tid1, comm2, tid2)
            current += period
            self.write_sched_switch(current, cpu_id, comm2, tid2, comm1, tid1)
            current += period

    def compare_output(self, cmd, expected):
        result = subprocess.getoutput(cmd)
        diff = difflib.ndiff(expected.split('\n'), result.split('\n'))
        txt = ""
        ok = True
        for l in diff:
            if l[0] != ' ':
                ok = False
            txt = txt + (l) + '\n'
        if not ok:
            print(txt)
        return ok


class AnalyzesTest():
    def __init__(self, delete_trace=True, verbose=False):
        self.verbose = verbose
        self.t = TestTrace(delete_trace=delete_trace)
        self.common_options = '--no-progress --skip-validation'
        self.cmd_root = './'

    def log(self, msg):
        if self.verbose:
            print(msg)

    def compare_output(self, cmd, expected):
        return self.t.compare_output(cmd, expected)

    def run(self):
        ok = True
        self.write_trace()
        for t in self.test_list:
            ret = t[1]()
            self.log('%s: %s' % (t[0], ret))
            if not ret:
                ok = False
        return ok
