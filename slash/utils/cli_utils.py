from __future__ import print_function
import argparse
import os
import sys
from contextlib import contextmanager

import colorama

from .. import conf, plugins
from .._compat import cStringIO, iteritems, itervalues


_PLUGIN_ACTIVATION_PREFIX = "--with-"
_PLUGIN_DEACTIVATION_PREFIX = "--without-"

def add_pending_plugins_from_commandline(argv):
    returned_argv = []
    for arg in argv:
        if arg.startswith(_PLUGIN_DEACTIVATION_PREFIX):
            plugin_name = arg[len(_PLUGIN_DEACTIVATION_PREFIX):]
            plugins.manager.deactivate_later(plugin_name)
        elif arg.startswith(_PLUGIN_ACTIVATION_PREFIX):
            plugin_name = arg[len(_PLUGIN_ACTIVATION_PREFIX):]
            plugins.manager.activate_later(plugin_name)
        else:
            returned_argv.append(arg)
    return returned_argv

def configure_arg_parser_by_plugins(parser):
    for plugin in itervalues(plugins.manager.get_installed_plugins()):
        group = parser.add_argument_group('Options for --with-{0}'.format(plugin.get_name()))
        plugin.configure_argument_parser(group)

def configure_arg_parser_by_config(parser, config=None):
    if config is None:
        config = conf.config

    plugin_groups = {}

    parser.add_argument(
        "-o", dest="config_overrides", metavar="PATH=VALUE", action="append",
        default=[],
        help="Provide overrides for configuration"
    )
    for path, node, cmdline in _iter_cmdline_config(config):
        if path.startswith('plugin_config.'):
            plugin_name = path.split('.')[1]
            subparser = plugin_groups.get(plugin_name)
            if subparser is None:
                subparser = plugin_groups[plugin_name] = parser.add_argument_group(
                    'options for the {0} plugin (--with-{0})'.format(plugin_name))
        else:
            subparser = parser
        cmdline.configure_parser(subparser, path, node)

def configure_plugins_from_args(args):
    for plugin in itervalues(plugins.manager.get_active_plugins()):
        plugin.configure_from_parsed_args(args)

def _iter_cmdline_config(config):
    for path, cfg in config.traverse_leaves():
        cmdline = (cfg.metadata or {}).get("cmdline")
        if cmdline is None:
            continue
        yield path, cfg, cmdline

@contextmanager
def get_modified_configuration_from_args_context(parser, args, config=None):
    if config is None:
        config = conf.config
    to_restore = []
    try:
        for path, cfg, cmdline in _iter_cmdline_config(config):
            old_value = cfg.get_value()
            new_value = cmdline.update_value(old_value, args)
            if new_value != old_value:
                to_restore.append((path, cfg.get_value()))
                config.assign_path(path, new_value, deduce_type=True, default_type=str)
        for override in args.config_overrides:
            if "=" not in override:
                parser.error("Invalid config override: {0}".format(override))
            path, _ = override.split("=", 1)
            to_restore.append((path, config.get_path(path)))
            try:
                config.assign_path_expression(override, deduce_type=True, default_type=str)
            except ValueError:
                parser.error("Invalid value for config override: {0}".format(override))
        yield
    finally:
        for path, prev_value in reversed(to_restore):
            config.assign_path(path, prev_value)

class SlashArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super(SlashArgumentParser, self).__init__(
            prog=self._deduce_program_name(),
            usage='{} [options]'.format( self._deduce_program_name()),
            *args, **kwargs)

        self._positionals_metavar = None

    def _deduce_program_name(self):
        returned = os.path.basename(sys.argv[0])
        if len(sys.argv) > 1:
            returned += " {0}".format(sys.argv[1])
        return returned

    def set_positional_metavar(self, metavar):
        self._positionals_metavar = metavar
        self.usage += ' {0} [{0} [...]]'.format(metavar)

    def _iter_available_plugins(self):
        active_plugin_names = set(plugins.manager.get_active_plugins())
        for plugin_name, plugin in iteritems(plugins.manager.get_installed_plugins()):
            if plugin_name not in active_plugin_names:
                yield plugin_name, plugin

class Argument(object):
    """
    helper to defer initialization of cmdline parsers to later stages
    """
    def __init__(self, *args, **kwargs):
        super(Argument, self).__init__()
        self.args = args
        self.kwargs = kwargs

COLOR_RESET = colorama.Fore.RESET + colorama.Back.RESET + colorama.Style.RESET_ALL  # pylint: disable=no-member


def make_styler(style):
    return lambda s: '{0}{1}{2}'.format(style, s, COLOR_RESET)

UNDERLINED = '\x1b[4m'


class Printer(object):

    def __init__(self, report_stread, enable_output=True):
        self._stream = report_stread
        self._output_enabled = enable_output

    def _colored_print(self, *args):
        print(*args, file=self._stream)

    def __call__(self, *args):
        if self._output_enabled:
            self._colored_print(*args)


def error_abort(message, *args):
    if args:
        message = message.format(*args)
    print(message, file=sys.stderr)
    sys.exit(-1)
