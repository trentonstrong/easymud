"""

This module contains the primary implementation of the MUD engine.  It consists primarily
of domain classes to model game state and the entity/component/system implementation for game
entities.



"""

import logging
from uuid import uuid4 as uuid


class World(object):
    def __init__(self, definition):
        self.validate(definition)
        self.build(definition)
        self.initialize_managers()
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
        for component, manager in self.managers.items():
            logging.info("Running on_tick for %s" % component)
            manager.on_tick()
            logging.info("Finished on_tick for %s" % component)
        pass

    def initialize_managers(self):
        self.managers = dict([(component, manager(self)) for component, manager
                              in component_managers.items()])

    def get_manager(self, component):
        return self.managers[component]

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
            return ()
        return ((exit_dir, self.world.get_room(exit_id)) for exit_dir, exit_id in self.exit_dict.items())

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

    def add_component(self, component, attrs={}):
        if component not in self.components:
            self.components.append(component)
            manager = self.world.get_manager(component)
            manager.register(self, attrs)
        return self

    def remove_component(self, component):
        if component in self.components:
            self.components.remove(component)
            manager = self.world.get_manager(component)
            manager.unregister(self)
        return self

    def get_component(self, component):
        if component in self.components:
            manager = self.world.get_manager(component)
            return manager.get_attrs(self)
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

component_managers = {}


def register_component_manager(name, manager):
    component_managers[name] = manager


class ComponentManagerMetaclass(type):
    def __new__(cls, clsname, bases, attrs):
        klass = super(ComponentManagerMetaclass, cls).__new__(cls, clsname, bases, attrs)
        if clsname == "ComponentManager":
            return klass
        component = attrs.get('component')
        if component is None:
            raise TypeError("'component' not defined for component manager %s" % clsname)
        register_component_manager(component, klass)
        return klass


class ComponentManager(object):
    __metaclass__ = ComponentManagerMetaclass

    component = None

    requires = []

    defaults = {}

    def __init__(self, world):
        self.entities = {}
        self.world = world
        self.initialize()

    def initialize(self):
        pass

    def on_tick(self):
        pass

    def register(self, entity, attrs):
        if entity.id not in self.entities:
            for required_component in self.__class__.requires:
                entity.add_component(required_component)
            merge = self.__class__.defaults.copy()
            merge.update(attrs)
            self.set_attrs(entity, merge)
            self.on_register(entity)

    def on_register(self, entity):
        pass

    def unregister(self, entity):
        # TODO: Unload components required by this component
        if entity.id in self.entities:
            del self.entities[entity.id]
            self.on_unregister(entity)

    def on_unregister(self, entity):
        pass

    def get_attrs(self, entity):
        return self.entities[entity.id]

    def set_attrs(self, entity, attrs):
        self.entities[entity.id] = attrs

    def get(self, entity, attr):
        if entity.id in self.entities:
            return self.entities[entity.id].get(attr)
        return None

    def set(self, entity, attr, value):
        if entity.id in self.entities:
            self.entities[entity.id][attr] = value


class PlayerComponentManager(ComponentManager):
    component = "player"

    requires = ['mobile']

    defaults = {
        'session': None
    }

    def on_register(self, entity):
        entity.add_handler("moved", self.player_moved)
        # add session to entity for convenience
        entity.session = self.get(entity, 'session')

    def player_moved(self, entity, data=None):
        room = data['room']
        entity.session.display_room(room)


class MobileComponentManager(ComponentManager):
    component = 'mobile'

    defaults = {
        'room': 'root'
    }

    def on_register(self, entity):
        entity.add_handler("move", self.move)

    def move(self, entity, direction):
        room = self.get(entity, 'room')
        if room.get_exit(direction):
            self.set(entity, 'room', room.get_exit(direction))
            entity.send("moved", {
                'room': room.get_exit(direction)})
            return True
        return False
