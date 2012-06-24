"""

This module contains the primary implementation of the MUD engine.  It consists primarily
of domain classes to model game state and the entity/component/system implementation for game
entities.



"""
import logging
from uuid import uuid4 as uuid
from recordtype import recordtype


class EventDispatcher(object):
    def __init__(self, context):
        self.context = context
        self.listeners = {}

    def dispatch(self, event, **kwargs):
        for listener in self.listeners.get(event, ()):
            try:
                listener(self.context, **kwargs)
            except Exception as e:
                logging.exception(e)

    def add_handler(self, event, handler):
        event_listeners = self.listeners.get(event, [])
        if handler not in event_listeners:
            event_listeners.append(handler)
            self.listeners[event] = event_listeners
        return self

    def remove_handler(self, event, handler):
        event_listeners = self.listeners.get(event, [])
        if event_listeners:
            event_listeners.remove(handler)
            self.listeners[event] = event_listeners
        return self


class World(object):
    def __init__(self, definition):
        self.dispatcher = EventDispatcher(self)
        self.entities = {}
        self.entity_room_map = {}
        self.validate(definition)
        self.build(definition)
        self.initialize_systems()
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

    def where_entity(self, entity):
        return self.entity_room_map.get(entity.id)

    def move_entity(self, entity, room):
        self.entity_room_map[entity.id] = room

    def create_entity(self, room=None):
        if room is None:
            room = self.root
        entity = Entity(self)
        self.entities[entity.id] = entity
        self.entity_room_map[entity.id] = room
        return entity


class WorldValidationError(Exception):
    pass


class Room(object):
    def __init__(self, world, id, title, description, exits={}, entities=[]):
        self.dispatcher = EventDispatcher(self)
        self.world = world
        self.id = id
        self.title = title
        self.description = description.replace("\t", "")
        self.exit_dict = exits
        self.entities = entities

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
        self.dispatcher = EventDispatcher(self)
        self.id = str(uuid())
        self.world = world
        self.components = []

    def room():
        doc = "Entity's current room."
        def fget(self):
            return self.world.where_entity(self)
        def fset(self, value):
            self.world.move_entity(self, value)
        return locals()
    room = property(**room())

    def move(self, direction):
        prev_room = self.room
        next_room = prev_room.get_exit(direction)
        if next_room is not None:
            self.room = next_room
            next_room.dispatcher.dispatch("arrived", entity=self)
            self.dispatcher.dispatch("moved", from_room=prev_room, to_room=next_room)
            prev_room.dispatcher.dispatch("left", entity=self, direction=direction)
            return (True, None)
        return (False, "You cannot go that way.")

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

    requires = ['health']

    attributes = [('session', None)]


    def on_register(self, entity):
        entity.dispatcher.add_handler("moved", self.player_moved)
        # add session to entity for convenience
        player = self.get_component(entity)
        entity.session = player.session
        entity.room.dispatcher.add_handler("arrived", entity.session.display_entity_arrived)
        entity.room.dispatcher.add_handler("left", entity.session.display_entity_left)

    def player_moved(self, entity, **kwargs):
        from_room = kwargs['from_room']
        to_room = kwargs['to_room']
        from_room.dispatcher.remove_handler("arrived", entity.session.display_entity_arrived)
        from_room.dispatcher.remove_handler("left", entity.session.display_entity_left)
        entity.session.display_room(to_room)
        to_room.dispatcher.add_handler("arrived", entity.session.display_entity_arrived)
        to_room.dispatcher.add_handler("left", entity.session.display_entity_left)


class MobileComponentSystem(ComponentSystem):
    component = 'mobile'


class HealthComponentSystem(ComponentSystem):
    component = 'health'

    attributes = [
        ('hp', 100),
        ('hp_max', 100),
        ('hp_regen', 10),
        ('is_dead', False)]

    def on_register(self, entity):
        pass

    def on_tick(self):
        for entity, health in self.entities.items():
            # don't regen dead or fully healed entities
            if health.hp == health.hp_max or health.is_dead:
                continue

            if (health.hp + health.hp_regen) > health.hp_max:
                health.hp += (health.hp_max - health.hp)
            else:    
                health.hp += health.hp_regen

class ArmorComponentSystem(ComponentSystem):
    component = 'armor'

    attributes = ['ac']

    defaults = {
        'ac': 10
    }
