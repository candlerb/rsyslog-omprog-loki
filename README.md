# rsyslog to loki adapter

This is an experimental plugin to be run under omprog in rsyslog.  It
accepts batches of messages (in transactions) and forwards them to the
[loki API](https://github.com/grafana/loki/blob/master/docs/loki/api.md).

It requires messages to be in the following form:

```
yyyy-mm-ddTHH:MM:SS.ssssss-ZZ:ZZ {label="value",...} Message goes here
```

which can be built using an rsyslog template.

## Example configuration

```
template(name="loki" type="list") {
  property(name="timegenerated" dateformat="rfc3339" date.inUTC="on")
  constant(value=" {job=\"rsyslog\"")
  constant(value=",src_ip=\"")
  property(name="fromhost-ip" format="json")
  constant(value="\",hostname=\"")
  property(name="hostname" format="json")
  constant(value="\",facility=\"")
  property(name="syslogfacility-text" format="json")
  constant(value="\",severity=\"")
  property(name="syslogseverity-text" format="json")
  constant(value="\"} ")
  # Already escaped if EscapecontrolCharactersOnReceive is on (default)
  property(name="msg" controlcharacters="escape")
  constant(value="\n")
}

local0.*  action(type="omprog"
  template="loki"
  binary="/usr/local/sbin/omprog-loki.py"
  action.resumeInterval="5"
  confirmMessages="on"
  useTransactions="on"
  output="/tmp/loki.err"
  #queue.type="LinkedList"
  #queue.minDequeueBatchSize="50"   # only in 8.1901.0+
  #reportFailures="on"              # only in 8.38.0+
  forceSingleInstance="on")
```

Under light load, rsyslog will send one message per transaction, causing a
separate HTTP POST to loki.  To delay messages for batching you will need
rsyslog v8.1901.0 or later with the
[queue.minDequeueBatchSize](https://www.rsyslog.com/doc/master/rainerscript/queue_parameters.html#queue-mindequeuebatchsize)
[feature](https://github.com/rsyslog/rsyslog/issues/495).

## Caveats

Errors in your template can send `**INVALID PROPERTY NAME**` without a
newline, and the external prog will hang waiting for one.

If you use `timereported` instead of `timegenerated`, beware that devices
with wrong clocks may result in messages being thrown away by loki for being
too old.

Be careful with your label set: do not include any high-cardinality
properties.  For example, `programname` is probably OK, but `syslogtag`
(which includes the PID) probably is not.  This is because Loki creates a
new timeseries for every distinct combination of label values seen.

The message scanning in `omprog-loki.py` currently isn't quite right, and
can be confused by label values which start with `}` followed by space.

## Licence

This work is released under GPLv3 (same as rsyslog itself)
