from trie import Trie

# Stop words are words which should be considered part of the syntax of the
# command and can be removed w.l.o.g.
STOP_WORDS = ('at', 'in', 'to', 'the', 'on')


def parse_command(text):
    parts = [word.lower() for word in text.split(' ')
             if word not in STOP_WORDS]
    return (parts[0], parts[1:])


def dispatch(session, command_text):
    if not command_text:
        return None
    (command, args) = parse_command(command_text)
    command_matches = commands.retrieve(command + '*')
    if not command_matches:
        session.display("You don't remember how to %s" % command)
        return None
    first_match = command_matches[0]
    command = first_match[0]
    command_func = first_match[1]
    return command_func(command, session, *args)


def move(cmd, session):
    direction = cmd
    mobile = session.world.get_manager('mobile')
    moved = mobile.move(session.player, direction)
    if not moved:
        session.display('You cannot go %s' % direction)
    return True


def help(cmd, session):
    """
    The presence within your mind seems to shrug or shake it heads at you.
    It can't help you with %s
    """
    pass


def say(cmd, session, message, target=None):
    """
    Echoes message text to other objects in room
    """


def inspect(cmd, session, target=None):
    if target is None:
        session.display_room(session.player.room)
    return True


def inventory(cmd, session):
    pass


def build_commands(definitions):
    """ Builds an in-memory prefix tree for command parsing """
    command_tree = Trie()
    for command in COMMAND_DEFINITIONS:
        command_tree.insert(command[0], command)
    return command_tree

COMMAND_DEFINITIONS = (
#    Command        Function     Help
    ("north",       move,       "Moves the character one room north"),
    ("south",       move,       "Moves the character one room south"),
    ("east",        move,       "Moves the character one room east"),
    ("west",        move,       "Moves the character one room west"),
    ("help",        help,       "Shows this help menu"),
    ("say",         say,        "Make your voice heard"),
    ("look",        inspect,    "A synonym for inspect"),
    ("inspect",     inspect,    "Take a closer look at an object"),
    ("inventory",   inventory,  "Have a look at your other worldly possessions")
)
commands = build_commands(COMMAND_DEFINITIONS)


class CommandNotFound(Exception):
    def __init__(self, command):
        self.command = command

    def __unicode__(self):
        return "Command not found: %s" % self.command
