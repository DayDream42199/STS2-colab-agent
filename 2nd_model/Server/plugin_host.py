"""The optional server plugin: loading it, and keeping the game safe from it.

A plugin is a module under Server/Plugins/, named by config.PLUGIN, with a
`create_plugin()` function returning an object. Every method on that object
is optional, and each is given the Session first, so it can read anything
(session.combat, session.players, session.roles) without holding on to it:

    format_message(session, recipient, role, message)
        -> the message to send that recipient, or None to send them nothing.
           `message` is a copy of what the player format would send; `role`
           is what that client said it is ("player" if it said nothing).
    on_identify(session, unit_id, role)
    on_combat_start(session)
    on_turn_start(session)                 the players' turn has begun
    on_action(session, action)             a play or an answer: see COMBAT_INTERFACE.md
    on_turn_ended(session, unit_id)        before the turn can move on
    on_round_end(session)                  everyone has ended; the enemies are next
    on_player_left(session, unit_id)
    on_combat_end(session, result)

What the server promises:
- No plugin file: nothing is called and every message goes out in the
  player format, exactly as without this module.
- A plugin that fails to load, or raises, is reported on the console and the
  game carries on: a failing hook is skipped, and a failing format_message
  sends that message in the player format.
- Values handed to the plugin are the engine's own, in game units. Turning
  them into network inputs (tanh, soft scales, one-hots) belongs to the AI's
  side, not here.
"""
import copy
import importlib
import traceback


class NullPlugin:
    """No plugin: the session formats nothing and calls nothing."""
    active = False

    def call(self, hook, *args):
        return None

    def format(self, session, recipient, role, message):
        return message


class PluginGuard:
    """Calls into a loaded plugin, so that nothing it does can stop the game."""
    active = True

    def __init__(self, plugin, name="plugin"):
        self.plugin = plugin
        self.name = name
        self._reported = set()

    def _report(self, where):
        # The whole traceback the first time, a line after that, so a hook
        # failing every turn does not bury the console.
        if where not in self._reported:
            self._reported.add(where)
            print(f"[{self.name}] {where} raised; the game carries on without it:")
            traceback.print_exc()
        else:
            print(f"[{self.name}] {where} raised again.")

    def call(self, hook, *args):
        method = getattr(self.plugin, hook, None)
        if method is None:
            return None
        try:
            return method(*args)
        except Exception:
            self._report(hook)
            return None

    def format(self, session, recipient, role, message):
        method = getattr(self.plugin, "format_message", None)
        if method is None:
            return message
        try:
            # A copy: one message object goes to every recipient, and a
            # plugin reshaping it for one must not change it for the others.
            return method(session, recipient, role, copy.deepcopy(message))
        except Exception:
            self._report("format_message")
            return message


def load_plugin(name):
    """The plugin `name` names (e.g. "Plugins.aura"), or a NullPlugin when
    there is none - no name, no such file, or one that does not load."""
    if not name:
        return NullPlugin()
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name and (name == error.name or name.startswith(error.name + ".")):
            print(f"No plugin {name!r} found: sending the player format only.")
        else:
            print(f"Plugin {name!r} could not load; sending the player format only:")
            traceback.print_exc()
        return NullPlugin()
    except Exception:
        print(f"Plugin {name!r} could not load; sending the player format only:")
        traceback.print_exc()
        return NullPlugin()

    factory = getattr(module, "create_plugin", None)
    if factory is None:
        print(f"Plugin {name!r} has no create_plugin(); sending the player format only.")
        return NullPlugin()
    try:
        plugin = factory()
    except Exception:
        print(f"Plugin {name!r}: create_plugin() raised; sending the player format only:")
        traceback.print_exc()
        return NullPlugin()
    print(f"Plugin {name!r} loaded.")
    return PluginGuard(plugin, name)
