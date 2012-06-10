"""
Classes and functions for dealing with player session communication.

The primary class here is the session object, which centralizes state
and provides the API for client <-> server communication.
"""
import jinja2
from jinja2 import contextfilter

ANSI_RESET = '\033[0m'

ANSI_COLORS = {
    'black':            ('#000000', '\033[30m', '\033[40m'),
    'red':              ('#cd0000', '\033[31m', '\033[41m'),
    'green':            ('#00cd00', '\033[32m', '\033[42m'),
    'yellow':           ('#cdcd00', '\033[33m', '\033[43m'),
    'blue':             ('#0000ee', '\033[34m', '\033[44m'),
    'magenta':          ('#cd00cd', '\033[35m', '\033[45m'),
    'cyan':             ('#00cdcd', '\033[36m', '\033[46m'),
    'grey':             ('#e5ffff', '\033[37m', '\033[47m'),
    'dark grey':        ('#7f7f7f', '\033[1;30m', '\033[1;40m'),
    'bright red':       ('#ff0000', '\033[1;31m', '\033[1;41m'),
    'bright green':     ('#00ff00', '\033[1;32m', '\033[1;42m'),
    'bright yellow':    ('#ffff00', '\033[1;33m', '\033[1;43m'),
    'purple':           ('#5c5cff', '\033[1;34m', '\033[1;44m'),
    'bright magenta':   ('#ff00ff', '\033[1;35m', '\033[1;45m'),
    'bright cyan':      ('#00ffff', '\033[1;36m', '\033[1;46m'),
    'white':            ('#ffffff', '\033[1;37m', '\033[1;47m')
}


@contextfilter
def color_filter(context, text, color, bgcolor=None):
    device = context['device']
    if color not in ANSI_COLORS:
        return text
    color = ANSI_COLORS.get(color)
    bgcolor = ANSI_COLORS.get(bgcolor, None)

    if device == 'web':
        color = color[0]
        if bgcolor is None:
            bgcolor = ''
        return "[[;%s;%s;]%s]" % (color, bgcolor, text)

    elif device == 'terminal':
        color = color[1]
        if bgcolor is not None:
            color = color + bgcolor[1]
        return color + text + ANSI_RESET

    return text


filters = {
    'color': color_filter
}

environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader('mud_templates'),
    bytecode_cache=jinja2.FileSystemBytecodeCache('mud_templates/cache'),
#    newline_sequence='\r\n',
    auto_reload=True)
environment.filters.update(filters)


def render_template(template, context=None):
    template = environment.get_template(template)
    return template.render(context)


class Session(object):
    def __init__(self, socket, world):
        self.socket = socket
        self.world = world
        self.player = self.world.create_entity() \
            .add_component('mobile', {'room': self.world.root}) \
            .add_component('player', {'session': self})

    def start(self):
        mobile = self.player.get_component('mobile')
        self.display_room(mobile.get('room'))

    def display(self, text):
        return self.socket.write_message(text)

    def display_template(self, template, context={}):
        context['device'] = self.socket.device
        return self.display(render_template(template, context))

    def display_room(self, room):
        return self.display_template('world/room.txt', {'room': room})

    def prompt(self, text, callback):
        self.display(text, 'red')
        self.prompt = (text, callback)
