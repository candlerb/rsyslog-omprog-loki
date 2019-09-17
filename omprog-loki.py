#!/usr/bin/env python3

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import functools
import re
import requests
import sys
import time

# Include the trailing \n in these
BEGIN_TRANSACTION_MARK = "BEGIN TRANSACTION\n"
COMMIT_TRANSACTION_MARK = "COMMIT TRANSACTION\n"
CONFIRM_MESSAGES = True

PUSH_URL = "http://localhost:3100/api/prom/push"
PUSH_OPT = {}

DEBUG = sys.stderr
#DEBUG = open("/tmp/debug.out", "a")

# We need to flush on every print()
print = functools.partial(print, flush=True)

def flush(events):
    """
    Send a batch as a single HTTP POST.  If there
    is a temporary error then return an error
    message, so that rsyslogd will retry
    """
    data = {"streams": [
        {
            "labels": labels,
            "entries": entries
        } for labels, entries in events.items()
    ]}
    r = requests.post(PUSH_URL, json=data, **PUSH_OPT)
    events.clear()
    if r.ok:
        return "OK"
    err = "Loki error: code %r: %s" % (r.status_code, r.text.replace("\n", " "))
    print(err, file=DEBUG)
    if 400 <= r.status_code <= 499:
        # We sent badly-formatted data to loki, no point retrying.
        # Beware https://github.com/grafana/loki/issues/929 (now fixed)
        return "OK"
    # Tell rsyslog of the error, it will resend all events to us
    return err

in_transaction = False
events = {}   # {labels: [{"ts":ts,"line":line}, ...]}

print("Starting...", file=DEBUG)
if CONFIRM_MESSAGES:
    print("OK") # signal we are ready
for line in sys.stdin:
    #print(repr(line), file=DEBUG)
    if line == BEGIN_TRANSACTION_MARK:
        in_transaction = True
        if CONFIRM_MESSAGES:
            print("OK")
        continue
    if line == COMMIT_TRANSACTION_MARK:
        #####################
        ## This can force batching under light load for
        ## old rsyslog without queue.minDequeueBatchSize
        ## (but risks losing messages under high load)
        #if len(events) < 5:
        #    time.sleep(0.5)
        #####################
        in_transaction = False
        res = flush(events)
        if CONFIRM_MESSAGES:
            print(res)
        continue
    # FIXME: this doesn't handle pathological cases like {foo="} "}
    m = re.match(r'^([0-9T:.+-]+) (\{.+?[^\\]"\}) (.*)$', line)
    if not m:
        # This line is badly formatted: we don't want to receive it again
        print("Invalid line: %r" % line, file=DEBUG)
        if CONFIRM_MESSAGES:
            print("DEFER_COMMIT" if in_transaction else "OK")
        continue
    ts, labels, line = m.group(1), m.group(2), m.group(3)
    if labels not in events:
        events[labels] = []
    events[labels].append({"ts":ts, "line":line})
    if in_transaction:
        if CONFIRM_MESSAGES:
            print("DEFER_COMMIT")
        continue
    # If transaction mode not in use, flush and acknowledge
    # messages one by one.  This is not very efficient.
    res = flush(events)
    if CONFIRM_MESSAGES:
        print(res)
