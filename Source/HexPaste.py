# -*- coding: utf-8 -*-

"""
HexPaste.
An HexChat plugin that pastes files line by line on IRC.
"""


__module_name__ = 'HexPaste'
__module_version__ = '2014.01.10'
__module_description__ = 'Paste files line by line on IRC.'


import traceback
import xchat


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

    except (OSError, UnicodeError) as err:
        raise HexPasteError('HexPaste: unable to read: %s - %s.' % (filepath, str(err)))


def parse_speed(string):
    """
    Read the parsing speed from 'string' and validate it.
    Errors are wrapped as HexPasteError instances.
    """
    try:
        speed = int(string)

        if not speed > 0:
            raise HexPasteError('HexPaste: speed must be positive.')

        return speed

    except ValueError:
        raise HexPasteError('HexPaste: invalid speed: %s.' % string)


def paste_line(context, line):
    """
    Say 'line' in a given HexChat 'context'.
    Empty lines are converted to a single space.
    """
    line = line.rstrip() or ' '
    context.command('say %s' % line)


# Data representation:

class MessageContext(object):
    """
    Represents a context (network/server/channel) where messages can be pasted.

    Since xchat.get_context() returns an unhashable object, this class
    serves the same purpose. Like the former, MessageContext() returns
    a representation of the current active context.

    Two instances of 'MessageContext' are considered equal when the network
    server and channel are equal.
    """

    def __init__(self):
        self.network = xchat.get_info('network')
        self.server = xchat.get_info('server')
        self.channel = xchat.get_info('channel')

    def __eq__(self, other):
        return ((self.network == other.network)
            and (self.server == other.server)
            and (self.channel == other.channel))

    def __hash__(self):
        return hash((self.network, self.server, self.channel))

    def __str__(self):
        return '%s - %s' % (self.channel, self.network)


class Message(object):
    """ Represents the state of a message that is being pasted in a given context. """

    def __init__(self, parent, context, lines, speed):

        # parent HexPaste instance that created this message:
        self.parent = parent

        # target context where we will be pasting:
        self.context = context

        # message data:
        self.lines = lines
        self.line_number = 0
        self.total_lines = len(lines)

        # timer and pasting state:
        self.speed = speed
        self.hook = None
        self.state = 'stop'


    @property
    def remaining_lines(self):
        """ Total lines pending to paste. """
        return self.total_lines - self.line_number


    def paste(self):
        """ Start pasting lines in this message context. """

        if not self.state == 'stop':
            raise HexPasteError('HexPaste: already pasting to: %s.' % self.context)

        self.hook = xchat.hook_timer(self.speed, self.tick)
        self.state = 'paste'


    def stop(self):
        """ Stop pasting lines in this message context. """

        if not self.state == 'paste':
            raise HexPasteError('HexPaste: not pasting to: %s.' % self.context)

        xchat.unhook(self.hook)
        self.hook = None
        self.state = 'stop'


    def resume(self):
        """ Resume pasting lines in this message context. """

        if not self.state == 'stop':
            raise HexPasteError('HexPaste: no pending lines to: %s.' % self.context)

        self.hook = xchat.hook_timer(self.speed, self.tick)
        self.state = 'paste'


    def maybe_stop(self):
        """ Like 'Message.stop()' but does not raise errors when not pasting. """

        if self.state == 'paste':
            self.stop()


    def tick(self, userdata):
        """
        Continue pasting while active and pending lines.
        Auto-pauses when the context is unreachable.
        """
        xchat_context = xchat.find_context(self.context.server, self.context.channel)

        # no context, auto-pause:
        if xchat_context is None:
            xchat.prnt('HexPaste: stopping, target unreachable: %s.' % self.context)
            self.stop()
            return 0

        # no lines, notice parent and stop:
        if self.remaining_lines == 0:
            self.parent.remove_target(self.context)
            return 0

        line = self.lines[self.line_number]
        paste_line(xchat_context, line)
        self.line_number += 1
        return 1


class HexPaste(object):

    def __init__(self):

        # all the active targets, where the key is a MessageContext
        # and the value the Message being pasted in that context:
        self.targets = {}


    def remove_target(self, context):
        """ Messages call this to notice us when they are done pasting. """

        if not context in self.targets:
            raise HexPasteError('HexPaste: internal error, removing unknown context?!')

        del self.targets[context]
        xchat.prnt('HexPaste: no more lines, finished pasting to: %s.' % context)


    def paste(self, lines, speed):
        """ Start pasting lines to the current context. """
        context = MessageContext()

        # there is a message, stop and replace with the new message:
        if context in self.targets:
            old_message = self.targets[context]
            old_message.maybe_stop()
            xchat.prnt('HexPaste: replacing current message to: %s.' % context)

        message = Message(self, context, lines, speed)
        self.targets[context] = message
        message.paste()

        xchat.prnt('HexPaste: pasting (%s lines) to: %s.'
            % (message.remaining_lines, context))


    def stop(self):
        """ Stop pasting lines to the current context. """
        context = MessageContext()

        if not context in self.targets:
            raise HexPasteError('HexPaste: not pasting to: %s.' % context)

        message = self.targets[context]
        message.stop()

        xchat.prnt('HexPaste: stopped pasting (%s pending lines) to: %s.'
            % (message.remaining_lines, context))


    def resume(self):
        """ Resume pasting lines to the current target. """
        context = MessageContext()

        if not context in self.targets:
            raise HexPasteError('HexPaste: not pasting to: %s.' % context)

        message = self.targets[context]
        message.resume()

        xchat.prnt('HexPaste: resumed pasting (%s pending lines) to: %s.'
            % (message.remaining_lines, context))


# Action callbacks:

paster = HexPaste()

def hexpaste_paste_cb(word, word_eol, userdata):
    """ Paste a file in the current server/channel. """

    if len(word) < 3:
        raise HexPasteError('HexPaste: no filename.')

    filepath = word[2]
    speed = 2500

    if len(word) == 4:
        speed = parse_speed(word[3])

    lines = file_lines(filepath)
    paster.paste(lines, speed)


def hexpaste_stop_cb(word, word_eol, userdata):
    """ Stop pasting in the current server/channel. """
    paster.stop()


def hexpaste_resume_cb(word, word_eol, userdata):
    """ Resume pasting in the current server/channel. """
    paster.resume()


hexpaste_actions = {
    'paste'  : hexpaste_paste_cb,
    'stop'   : hexpaste_stop_cb,
    'resume' : hexpaste_resume_cb,
}


# Main callback:

def hexpaste_cb(word, word_eol, userdata):
    """ Parse parameters and dispatch to particular actions. """

    try:
        if len(word) < 2:
            raise HexPasteError('HexPaste: no parameters.')

        action = word[1]
        if not action in hexpaste_actions:
            raise HexPasteError('HexPaste: unknown action: %s.' % action)

        hexpaste_actions[action](word, word_eol, userdata)

    except HexPasteError as err:
        xchat.prnt(str(err))

    # HexChat tends to eat exceptions without any message or traceback,
    # force printing for any unknown error:
    except Exception:
        xchat.prnt(traceback.format_exc())

    finally:
        return xchat.EAT_ALL


xchat.hook_command('hexpaste', hexpaste_cb)


# Done:

xchat.prnt('%s %s loaded.' % (__module_name__, __module_version__))

