"""

This module contains the primary implementation of the MUD engine.  It consists primarily
of domain classes to model game state and the entity/component/system implementation for game
entities.



"""

import logging
from uuid import uuid4 as uuid
from recordtype import recordtype


class World(object):
    def __init__(self, definition):
        self.validate(definition)
        self.build(definition)
        self.initialize_systems()
        self.entities = {}
        self.current_tick = 0

    def validate(self, definition):
        for room in definition.values():
            for direction, exit in room.get('exits', {}).items():
                if exit not in definition:
                    raise WorldValidationError("exit %s not valid" % exit)

        return True

    def build(self, definition):
        self.rooms = dict([
            (id,
             Room(
                self,
                id,
                room.get('title', 'An Unnamed Room'),
                "\n".join([line.strip() for line in room.get('description', '').split("\n")]),
                room.get('exits', {}),
                room.get('objects', [])))
            for id, room in definition.items()])

    def tick(self):
        """
        The oh-so-famous tick.  Should be called at a set interval, but can be called
        manually in certain cases if you want to force a tick for some reason.
        """
        self.current_tick = self.current_tick + 1
        logging.info("Tick: %d" % self.current_tick)
        for component, system in self.systems.items():
            logging.info("Running on_tick for %s" % component)
            system.on_tick()
            logging.info("Finished on_tick for %s" % component)
        pass

    def initialize_systems(self):
        self.systems = dict([(component, system(self)) for component, system
                              in component_systems.items()])

    def get_system(self, component):
        return self.systems[component]

    @property
    def root(self):
        return self.get_room('root')

    def get_room(self, id):
        return self.rooms.get(id)

    def create_entity(self):
        entity = Entity(self)
        self.entities[entity.id] = entity
        return entity


class WorldValidationError(Exception):
    pass


class Room(object):
    def __init__(self, world, id, title, description, exits={}, objects=[]):
        self.world = world
        self.id = id
        self.title = title
        self.description = description.replace("\t", "")
        self.exit_dict = exits
        self.objects = objects

    def get_exit(self, direction):
        return self.world.get_room(self.exit_dict.get(direction))

    @property
    def exits(self):
        if self.exit_dict is None:
            return None
        return self.exit_dict.keys()

    def __unicode__(self):
        return self.title

    def __str__(self):
        return unicode(self).encode('utf-8')


### ENTITIES ###


class Entity(object):
    def __init__(self, world):
        self.id = uuid()
        self.world = world
        self.listeners = {}
        self.components = []

    def add_component(self, component, **kwargs):
        if component not in self.components:
            self.components.append(component)
            system = self.world.get_system(component)
            system.register(self, **kwargs)
        return self

    def remove_component(self, component):
        if component in self.components:
            self.components.remove(component)
            system = self.world.get_system(component)
            system.unregister(self)
        return self

    def get_component(self, component):
        if component in self.components:
            system = self.world.get_system(component)
            return system.get_component(self)
        return None

    def has_component(self, component):
        return component in self.components

    def requires(self, components):
        missing = (component for component in components if component not in self.components)
        for component in missing:
            self.add_component(component)
        return self

    def send(self, message, data=None):
        for listener in self.listeners.get(message):
            listener(self, data)

    def add_handler(self, message, handler):
        listeners = self.listeners.get(message, [])
        if handler not in listeners:
            listeners.append(handler)
            self.listeners[message] = listeners
        return self

    def remove_handler(self, message, handler):
        listeners = self.listeners[message]
        listeners.remove(handler)
        self.listener[message] = listeners
        return self

### COMPONENTS ###

component_systems = {}


def register_component_system(name, system):
    component_systems[name] = system


class ComponentSystemMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        klass = super(ComponentSystemMetaclass, cls).__new__(cls, clsname, bases, attrs)
        if clsname == "ComponentSystem":
            return klass
        component = attrs.get('component')
        if component is None:
            raise TypeError("'component' not defined for component system %s" % clsname)
        register_component_system(component, klass)
        return klass


class ComponentSystem(object):
    __metaclass__ = ComponentSystemMetaclass

    component = None

    attributes = []

    requires = []

    def __init__(self, world):
        self.entities = {}
        self.world = world
        self.record = recordtype(self.__class__.component, self.__class__.attributes)
        self.initialize()

    def initialize(self):
        pass

    def on_tick(self):
        pass

    def register(self, entity, **kwargs):
        if entity.id not in self.entities:
            for required_component in self.__class__.requires:
                entity.add_component(required_component)
            self.entities[entity.id] = self.record(**kwargs)
            self.on_register(entity)

    def on_register(self, entity):
        pass

    def unregister(self, entity):
        if entity.id in self.entities:
            del self.entities[entity.id]
            self.on_unregister(entity)

    def on_unregister(self, entity):
        pass

    def get_component(self, entity):
        return self.entities[entity.id]


class PlayerComponentSystem(ComponentSystem):
    component = "player"

    requires = ['mobile']

    attributes = [('session', None)]


    def on_register(self, entity):
        entity.add_handler("moved", self.player_moved)
        # add session to entity for convenience
        player = self.get_component(entity)
        entity.session = player.session

    def player_moved(self, entity, data=None):
        room = data['room']
        entity.session.display_room(room)


class MobileComponentSystem(ComponentSystem):
    component = 'mobile'

    attributes = ['room']

    defaults = {
        'room': 'root'
    }

    def on_register(self, entity):
        entity.add_handler("move", self.move)

    def move(self, entity, direction):
        mobile = self.get_component(entity)
        room = mobile.room
        if room.get_exit(direction):
            mobile.room = room.get_exit(direction)
            entity.send("moved", {
                'room': mobile.room})
            return True
        return False
