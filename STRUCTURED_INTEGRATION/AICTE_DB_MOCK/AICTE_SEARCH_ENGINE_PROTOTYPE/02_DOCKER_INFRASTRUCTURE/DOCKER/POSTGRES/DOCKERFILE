# Custom PostgreSQL image for the AICTE mock environment.
#
# The Debian tzdata shipped in the upstream postgres:16 image omits legacy
# backward-compatibility aliases: only /usr/share/zoneinfo/Asia/Kolkata exists,
# not Asia/Calcutta. Java clients such as DBeaver on Windows send their system
# timezone name ("Asia/Calcutta") as the TimeZone startup parameter, and the
# server rejects it with:
#   FATAL: invalid value for parameter "TimeZone": "Asia/Calcutta"
#
# PostgreSQL is built with --with-system-tzdata=/usr/share/zoneinfo, so
# restoring the alias as a symlink makes those connections work.
FROM postgres:16

RUN ln -s /usr/share/zoneinfo/Asia/Kolkata /usr/share/zoneinfo/Asia/Calcutta
