#!/bin/bash
# Run mail_import.py once from a scheduler such as cron.
#
# The importer prints counts and errors but no dates, so this wrapper writes the
# date and time of the start and the end of the run around its output. It also
# keeps two runs from overlapping, with flock. A POP3 mailbox takes one session
# at a time, so a run that starts while the previous one is still going would
# only fail at login.
#
# Everything is found relative to this file, so cron can start it by its full
# path from any directory.
#
#     */30 * * * * /path/to/pop3-to-gmail-import/tools/run_cron.sh
#
# cron mails whatever a job writes to standard output and standard error to the
# owner of the crontab. To keep a log file instead, redirect in the crontab line.
#
#     */30 * * * * /path/to/pop3-to-gmail-import/tools/run_cron.sh >> /var/log/pop3-to-gmail-import.log 2>&1
#
# The exit status is the importer's own, so a failure still reaches the caller.
# The one case this wrapper decides itself is a run that finds the lock held,
# which exits 0, since an overlap is not a failure.

set -eu

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
LOCK_FILE="$ROOT/.cron.lock"

timestamp() {
    date +%Y-%m-%dT%H:%M:%S%z
}

if ! command -v flock > /dev/null; then
    echo "error: flock not found. It is part of util-linux." >&2
    exit 1
fi

# File descriptor 9 holds the lock for the whole run. The kernel releases it
# when this shell exits, including when it is killed, so a run that dies does
# not leave the next one locked out.
exec 9> "$LOCK_FILE"
if ! flock -n 9; then
    echo "$(timestamp) not started, another run holds $LOCK_FILE"
    exit 0
fi

echo "$(timestamp) start"

status=0
python3 "$ROOT/mail_import.py" || status=$?

echo "$(timestamp) end status=$status seconds=$SECONDS"
exit "$status"
