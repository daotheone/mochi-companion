# Interfaces share SQLite directly until sync needs a service

The Character and the terminal are separate processes that open the same SQLite file, with no background service between them. A local service would not help the dual-boot setup, because it is off whenever Windows is booted, so #7 has to decide on hosting either way. `Companion` stays the only way into the data, so a service can wrap it when that decision is made.
