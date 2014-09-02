# -*- coding: utf-8 -*-

"""
HexPaste.
An HexChat plugin that pastes files line by line on IRC.
"""


__module_name__ = 'HexPaste'
__module_version__ = '2014.09.02'
__module_description__ = 'Paste files line by line on IRC.'


import collections
import hexchat
import traceback


# Error handling:

class HexPasteError(Exception):
    """ Custom class to discriminate between HexPaste and Python errors. """
    pass


# I/O and parsing utils:

def file_lines(filepath):
    """
    Open 'filepath' as UTF-8 and read a list of its lines.
    Errors are wrapped as HexPasteError instances.
    """
    try:
        with open(filepath, encoding = 'utf-8-sig') as descriptor:
            return descriptor.readlines()

    except (OSError, UnicodeDecodeError) as err:
        raise HexPasteError('HexPaste: unable to read: {} - {}.'.format(filepath, err))


def parse_speed(string):
    """
    Read the parsing speed from 'string' and validate it.
    Errors are wrapped as HexPasteError instances.
    """
    try:
        speed = int(string)

        if speed <= 0:
            raise HexPasteError('HexPaste: speed must be positive.')

        return speed

    except ValueError:
        raise HexPasteError('HexPaste: invalid speed: {}.'.format(string))


def paste_line(hexchat_context, line):
    """
    Say 'line' in a given hexchat context.
    Empty lines are converted to a single space.
    """
    line = line.rstrip()

    if len(line) == 0:
        line = ' '

    hexchat_context.command('say {}'.format(line))


# Data representation:

class MessageContext(object):
    """
    Represents a context (network/server/channel) where messages can be pasted.
    Since 'hexchat.get_context()' returns an unhashable object, this class
    serves the same purpose. Like the former, MessageContext() returns
    a representation of the current active context.
    """
    def __init__(self):
        self.id = hexchat.get_prefs('id')

        self.network = hexchat.get_info('network')
        self.server = hexchat.get_info('server')
        self.channel = hexchat.get_info('channel')

    def find_hexchat_context(self):
        """
        Try to find this context (e.g. like hexchat.find_context()).
        Returns None if unavailable.
        """
        for channel in hexchat.get_list('channels'):
            if channel.id == self.id:
                context = channel.context

                if ((context.get_info('network') == self.network)
                    and (context.get_info('server') == self.server)
                    and (context.get_info('channel') == self.channel)):
                    return context

        return None

    def __eq__(self, other):
        """
        Two instances are considered equal when the id, the network,
        the server and the channel are equal.
        """
        return (isinstance(other, MessageContext)
            and (self.id == other.id)
            and (self.network == other.network)
            and (self.server == other.server)
            and (self.channel == other.channel))

    def __hash__(self):
        return hash((self.id, self.network, self.server, self.channel))

    def __str__(self):
        return '{} - {}'.format(self.channel, self.network)


class Message(object):
    """ Represents the state of a message that is being pasted in a given context. """

    def __init__(self, parent, context, lines, speed):

        # parent HexPaste instance that created this message:
        self.parent = parent

        # MessageContext where we will be pasting:
        self.context = context

        # message data:
        self.lines = lines
        self.line_number = 0
        self.total_lines = len(lines)

        # timer and pasting state (either 'paste' or 'stop'):
        self.speed = speed
        self.hook = None
        self.state = 'stop'

    @property
    def remaining_lines(self):
        """ Total lines pending to paste. """
        return self.total_lines - self.line_number

    def paste(self):
        """ Continue pasting lines in this message context. """
        if self.state == 'paste':
            raise HexPasteError('HexPaste: already pasting to: {}.'.format(self.context))

        self.hook = hexchat.hook_timer(self.speed, self.tick)
        self.state = 'paste'

    def stop(self):
        """ Stop pasting lines in this message context. """
        if self.state == 'stop':
            raise HexPasteError('HexPaste: not pasting to: {}.'.format(self.context))

        hexchat.unhook(self.hook)
        self.hook = None
        self.state = 'stop'

    def maybe_stop(self):
        """ Like 'Message.stop()' but does not raise errors when not pasting. """
        if self.state == 'paste':
            self.stop()

    def tick(self, userdata):
        """
        Continue pasting while active and pending lines.
        Auto-stop when the context is unreachable.
        """
        # no lines, notice parent and stop the timer:
        if self.remaining_lines == 0:
            self.parent.remove_target(self.context)
            return 0

        hexchat_context = self.context.find_hexchat_context()

        # no context, auto-stop:
        if hexchat_context is None:
            hexchat.prnt('HexPaste: stopping, target unreachable: {}.'.format(self.context))
            self.stop()
            return 0

        line = self.lines[self.line_number]
        paste_line(hexchat_context, line)
        self.line_number += 1
        return 1


class HexPaste(object):
    """
    Mantains the collection of Messages that are currently active
    and provides commands for the current context.
    """
    def __init__(self):

        # all the active targets, where the key is a MessageContext
        # and the value the Message being pasted in that context:
        self.targets = {}

    def remove_target(self, context):
        """ Messages call this to notice us when they are done pasting. """

        if not context in self.targets:
            raise HexPasteError('HexPaste: internal error, removing unknown context?!')

        del self.targets[context]
        hexchat.prnt('HexPaste: finished pasting to: {}.'.format(context))

    def paste(self, lines, speed):
        """ Start pasting lines to the current context. """
        context = MessageContext()

        # there is a message, stop and replace it with the new message:
        if context in self.targets:
            old_message = self.targets[context]
            old_message.maybe_stop()
            hexchat.prnt('HexPaste: replacing message to: {}.'.format(context))

        message = Message(self, context, lines, speed)
        self.targets[context] = message
        message.paste()

        hexchat.prnt('HexPaste: pasting ({} lines) to: {}.'
            .format(message.remaining_lines, context))

    def stop(self):
        """ Stop pasting lines to the current context. """
        context = MessageContext()

        if not context in self.targets:
            raise HexPasteError('HexPaste: not pasting to: {}.'.format(context))

        message = self.targets[context]
        message.stop()

        hexchat.prnt('HexPaste: stopped pasting ({} pending lines) to: {}.'
            .format(message.remaining_lines, context))

    def resume(self):
        """ Resume pasting lines to the current context. """
        context = MessageContext()

        if not context in self.targets:
            raise HexPasteError('HexPaste: not pasting to: {}.'.format(context))

        message = self.targets[context]
        message.paste()

        hexchat.prnt('HexPaste: resumed pasting ({} pending lines) to: {}.'
            .format(message.remaining_lines, context))


# Globals:

paster = HexPaste()
hexpaste_commands = collections.OrderedDict()


# Add commands:

def hexpaste_file_cb(word, word_eol, userdata):
    """
    /hexpaste file path/to/file [speed]
      * Paste the lines of that file in the current active channel/query.
        The default speed is 2500 milliseconds.
    """
    if len(word) < 3:
        raise HexPasteError('HexPaste: no filename.')

    filepath = word[2]

    if len(word) >= 4:
        speed = parse_speed(word[3])
    else:
        speed = 2500

    lines = file_lines(filepath)
    paster.paste(lines, speed)


def hexpaste_stop_cb(word, word_eol, userdata):
    """
    /hexpaste stop
      * Stop pasting to the current active channel/query.
        After stopping, '/hexpaste resume' will continue
        pasting the pending lines.
    """
    paster.stop()


def hexpaste_resume_cb(word, word_eol, userdata):
    """
    /hexpaste resume
      * Continue pasting lines to the current active channel/query.
    """
    paster.resume()


def hexpaste_help_cb(word, word_eol, userdata):
    """
    /hexpaste help
      * Prints all the available commands.
    """
    hexchat.prnt('HexPaste: available commands:')

    for command in hexpaste_commands.values():
        hexchat.prnt(command.__doc__.rstrip())


hexpaste_commands['file'] = hexpaste_file_cb
hexpaste_commands['stop'] = hexpaste_stop_cb
hexpaste_commands['resume'] = hexpaste_resume_cb
hexpaste_commands['help'] = hexpaste_help_cb


# Main callback:

def hexpaste_cb(word, word_eol, userdata):
    """ Parse parameters and dispatch to particular commands. """
    try:
        if len(word) < 2:
            raise HexPasteError('HexPaste: no parameters. See "/hexpaste help" for documentation.')

        command = word[1]
        if not command in hexpaste_commands:
            raise HexPasteError('HexPaste: unknown command. See "/hexpaste help" for documentation.')

        hexpaste_commands[command](word, word_eol, userdata)

    except HexPasteError as err:
        hexchat.prnt(str(err))

    # HexChat tends to eat exceptions without any message or traceback,
    # force printing for any unknown error:
    except Exception:
        hexchat.prnt(traceback.format_exc())

    finally:
        return hexchat.EAT_ALL


hexchat.hook_command('hexpaste', hexpaste_cb)


# Done:

hexchat.prnt('{} {} loaded'.format(__module_name__, __module_version__))

