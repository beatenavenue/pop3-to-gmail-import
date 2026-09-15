"""The rule that decides which messages are deleted without being imported.

Copy this file to mail_filter.py and write the rule in the copy. mail_filter.py
is listed in .gitignore, since a real rule usually names real addresses.

mail_import.py calls should_discard() for every message it has not handled
before. If the function raises, that message is neither imported nor deleted,
and mail_import.py exits with a non-zero status after the other messages.
"""


def should_discard(message):
    """Return True to delete the message from the POP3 server without importing it.

    message is an email.message.EmailMessage parsed with email.policy.default,
    so header values come back decoded. Changing it has no effect, since the raw
    bytes fetched from the server are what gets imported. Some ways to read it
    are listed below.

        message["Subject"]               the subject, or None
        message["From"]                  the sender
        message.get_all("To", [])        every To header, and likewise "Cc"
        message["Date"].datetime         the date, when there is a Date header
        message.walk()                   every MIME part, the message included
        part.get_filename()              a part's attachment filename, or None
        part.get_payload(decode=True)    a part's decoded content as bytes
    """
    return False


# An example rule, which discards mail sent to a list when it carries an
# attachment. Put something like this in mail_filter.py.
#
# LIST_ADDRESS = "list@example.com"
#
# def should_discard(message):
#     headers = message.get_all("To", []) + message.get_all("Cc", [])
#     addresses = {a.addr_spec.lower() for header in headers for a in header.addresses}
#     has_attachment = any(part.get_filename() for part in message.walk())
#     return LIST_ADDRESS in addresses and has_attachment
