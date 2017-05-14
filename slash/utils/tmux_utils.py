import sys
import os
import libtmux
import logbook
from ..exceptions import TmuxSessionNotExist, TmuxExecutableNotFound

SESSION_NAME = 'slash_session'
TMUX_EXECUTABLE_NAME = 'tmux'
MASTER_WINDOW_NAME = 'master'

_logger = logbook.Logger(__name__)

def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None

def is_in_tmux():
    return os.environ.get('TMUX') is not None

def get_slash_tmux_session():
    try:
        tmux_server = libtmux.Server()
        return tmux_server.find_where({"session_name":SESSION_NAME})
    except libtmux.exc.LibTmuxException:
        _logger.debug('No tmux server is running')
        return

def create_new_window(window_name, command):
    slash_session = get_slash_tmux_session()
    if not slash_session:
        raise TmuxSessionNotExist("Slash tmux session not found, can't create new window")
    return slash_session.new_window(attach=False, window_name=window_name, window_shell=command)

def run_slash_in_tmux(command):
    tmux_session = get_slash_tmux_session()
    if tmux_session:
        libtmux.Server().switch_client(SESSION_NAME)
    else:
        path_to_tmux = which(TMUX_EXECUTABLE_NAME)
        if not path_to_tmux:
            _logger.error("Tmux executable not found")
            raise TmuxExecutableNotFound("Tmux executable not found")
        command = ' '.join([sys.executable, '-m', 'slash.frontend.main', 'run'] + command + [';$SHELL'])
        tmux_args = [path_to_tmux, 'new-session', '-s', SESSION_NAME, '-n', MASTER_WINDOW_NAME]
        if is_in_tmux():
            tmux_args.append('-Ad')
        tmux_args.append(command)
        os.execve(path_to_tmux, tmux_args, dict(os.environ))

def kill_tmux_session():
    get_slash_tmux_session().kill_session()
