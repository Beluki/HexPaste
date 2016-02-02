
## About

HexPaste is a Python 3 plugin for [HexChat][] that pastes files line by line
on IRC, with a specific delay between lines. I wrote it for a channel where
it's customary to paste poetry. It's similar to the [mIRC][] /play command.

[HexChat]: http://hexchat.github.io
[mIRC]: http://www.mirc.com

## Installation and usage

To install, just put the script in the HexChat addons folder. You'll need
HexChat 2.9.6+ with the Python 3 plugin. After installing you should see
the following messages on startup:

```bash
Python interface loaded
HexPaste 2016.02.02 loaded
```

The usage is simple:

* `/hexpaste file path/to/file [speed]` will paste the lines of that file
  in the current active channel/query. The default speed is 2500 milliseconds.

* `/hexpaste stop` will stop pasting to the current active channel/query. After
  stopping, you can resume pasting with `/hexpaste resume`.

* `/hexpaste help` will show all the available parameters and a description.

That's it. Commands always refer to the current active window. HexPaste supports
concurrent pastes to different channels/queries (even at different speeds).
You can pause one and keep others pasting, etc... Information messages will be
displayed on each operation, such as:

```
HexPaste: resumed pasting (N pending lines) to: channel - network.
```

When the original window that started the paste is no longer reachable, HexPaste
will auto-stop pasting lines. This makes it possible to continue pasting after
a network problem by joining the channel again and typing the command:
`/hexpaste resume`.

## Portability and notes

All input/output is done using UTF-8. HexPaste accepts input files with a BOM
signature (e.g. those created with the Windows notepad).

When pasting to multiple channels at once or using a small delay between lines
the timer may not be exact. This is due to network latency and to the `net_throttle`
setting in HexChat being active. Trying to paste faster would cause a disconnection
with an "Excess Flood" quit message.

Information and error messages are written to the current active window, regardless
of the paste channel. Rationale: notice which pastes complete, even when talking in
another channel/query.

Files are read entirely before pasting. Rationale: make sure pasting won't be
interrupted with decoding or IO errors.

HexPaste is tested on Windows 7 and 8 and on Debian (both x86 and x86-64)
using Python 3.3+ and HexChat 2.9.6+. Python 2.x is not supported.

## Status

This program is finished!

HexPaste is feature-complete and has no known bugs. Unless issues are reported
I plan no further development on it other than maintenance.

## License

Like all my hobby projects, this is Free Software. See the [Documentation][]
folder for more information. No warranty though.

[Documentation]: Documentation

