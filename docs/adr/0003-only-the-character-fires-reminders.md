# Only the Character fires Reminders and Check-ins

Reminders and Check-ins need something running on a clock, and the terminal blocks on `input()`, so only the Character can do it. The Character owns all timing and stores when each Task was reminded, each Snooze and each Focus Session in SQLite. The terminal can list and edit Tasks but never fires anything; at launch it only prints overdue ones. Because the Interfaces share one database (ADR 0002), a second timer in another process would double-fire, so do not "fix" the terminal by adding one. A future service (#7) may take over timing, and `Companion` stays the only way into the data so it can.

## Considered Options

- **Timers in every Interface**: rejected, because two processes on the same database would fire the same Reminder twice.
- **A background service now**: rejected for the reason in ADR 0002; it is off whenever Windows is booted, so it would not make Reminders reliable.
- **GNOME desktop notifications**: not adopted for now; a Reminder missed while the Character is hidden or behind a fullscreen app is accepted (see the issue).
