#!/usr/bin/env python
""" Which - locate a command

    * adapted from Brian Curtin's http://bugs.python.org/file15381/shutil_which.patch
    * see http://bugs.python.org/issue444582
    * uses ``PATHEXT`` on Windows
    * searches current directory before ``PATH`` on Windows,
      but not before an explicitly passed path
    * accepts both string or iterable for an explicitly passed path, or pathext
    * accepts an explicitly passed empty path, or pathext (either '' or [])
    * does not search ``PATH`` for files that have a path specified in their name already
    * moved defpath and defpathext lists initialization to module level,
      instead of initializing them on each function call
    * changed interface: which_files() returns generator, which() returns first match,
      or raises IOError(errno.ENOENT)

    .. function:: which_files(file [, mode=os.F_OK | os.X_OK[, path=None[, pathext=None]]])

       Return a generator which yields full paths in which the *file* name exists
       in a directory that is part of the file name, or on *path*,
       and has the given *mode*.
       By default, *mode* matches an inclusive OR of os.F_OK and os.X_OK - an 
       existing executable file.
       The *path* is, by default, the ``PATH`` variable on the platform,
       or the string/iterable passed in as *path*.
       In the event that a ``PATH`` variable is not found, :const:`os.defpath` is used.
       On Windows, a current directory is searched before using the ``PATH`` variable,
       but not before an explicitly passed *path*.
       The *pathext* is only used on Windows to match files with given extensions appended as well.
       It defaults to the ``PATHEXT`` variable, or the string/iterable passed in as *pathext*.
       In the event that a ``PATHEXT`` variable is not found,
       default value for Windows XP/Vista is used.
       The command is always searched without extension first,
       even when *pathext* is explicitly passed.

    .. function:: which(file [, mode=os.F_OK | os.X_OK[, path=None[, pathext=None]]])
       Return first match generated by which_files(file, mode, path, pathext),
       or raise IOError(errno.ENOENT).

"""
__docformat__ = 'restructuredtext en'
__all__ = 'which which_files pathsep defpath defpathext F_OK R_OK W_OK X_OK'.split()

import sys
from os import access, defpath, pathsep, environ, F_OK, R_OK, W_OK, X_OK
from os.path import exists, dirname, split, join
ENOENT = 2

windows = sys.platform.startswith('win')

defpath = environ.get('PATH', defpath).split(pathsep)

if windows:
    defpath.insert(0, '.') # can insert without checking, when duplicates are removed
    # given the quite usual mess in PATH on Windows, let's rather remove duplicates
    seen = set()
    defpath = [dir for dir in defpath if dir.lower() not in seen and not seen.add(dir.lower())]
    del seen

    defpathext = [''] + environ.get('PATHEXT',
        '.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC').lower().split(pathsep)
else:
    defpathext = ['']

def which_files(file, mode=F_OK | X_OK, path=None, pathext=None):
    """ Locate a file in a path supplied as a part of the file name,
        or the user's path, or a supplied path.
        The function yields full paths (not necessarily absolute paths),
        in which the given file name matches an existing file in a directory on the path.

        >>> def test_which(expected, *args, **argd):
        ...     result = list(which_files(*args, **argd))
        ...     assert result == expected, 'which_files: %s != %s' % (result, expected)
        ...
        ...     try:
        ...         result = [ which(*args, **argd) ]
        ...     except IOError:
        ...         result = []
        ...     assert result[:1] == expected[:1], 'which: %s != %s' % (result[:1], expected[:1])

        >>> if windows: cmd = environ['COMSPEC']
        >>> if windows: test_which([cmd], 'cmd')
        >>> if windows: test_which([cmd], 'cmd.exe')
        >>> if windows: test_which([cmd], 'cmd', path=dirname(cmd))
        >>> if windows: test_which([cmd], 'cmd', pathext='.exe')
        >>> if windows: test_which([cmd], cmd)
        >>> if windows: test_which([cmd], cmd, path='<nonexistent>')
        >>> if windows: test_which([cmd], cmd, pathext='<nonexistent>')
        >>> if windows: test_which([cmd], cmd[:-4])
        >>> if windows: test_which([cmd], cmd[:-4], path='<nonexistent>')

        >>> if windows: test_which([], 'cmd', path='<nonexistent>')
        >>> if windows: test_which([], 'cmd', pathext='<nonexistent>')
        >>> if windows: test_which([], '<nonexistent>/cmd')
        >>> if windows: test_which([], cmd[:-4], pathext='<nonexistent>')

        >>> if not windows: sh = '/bin/sh'
        >>> if not windows: test_which([sh], 'sh')
        >>> if not windows: test_which([sh], 'sh', path=dirname(sh))
        >>> if not windows: test_which([sh], 'sh', pathext='<nonexistent>')
        >>> if not windows: test_which([sh], sh)
        >>> if not windows: test_which([sh], sh, path='<nonexistent>')
        >>> if not windows: test_which([sh], sh, pathext='<nonexistent>')

        >>> if not windows: test_which([], 'sh', mode=W_OK)  # not running as root, are you?
        >>> if not windows: test_which([], 'sh', path='<nonexistent>')
        >>> if not windows: test_which([], '<nonexistent>/sh')
    """
    filepath, file = split(file)

    if filepath:
        path = (filepath,)
    elif path is None:
        path = defpath
    elif isinstance(path, str):
        path = path.split(pathsep)

    if pathext is None:
        pathext = defpathext
    elif isinstance(pathext, str):
        pathext = pathext.split(pathsep)

    if not '' in pathext:
        pathext.insert(0, '') # always check command without extension, even for custom pathext

    for dir in path:
        basepath = join(dir, file)
        for ext in pathext:
            fullpath = basepath + ext
            if exists(fullpath) and access(fullpath, mode):
                yield fullpath

def which(file, mode=F_OK | X_OK, path=None, pathext=None):
    """ Locate a file in a path supplied as a part of the file name,
        or the user's path, or a supplied path.
        The function returns full path (not necessarily absolute path),
        in which the given file name matches an existing file in a directory on the path,
        or raises IOError(errno.ENOENT).

        >>> # for doctest see which_files()
    """
    path = next(which_files(file, mode, path, pathext), None)
    if path is None:
        raise IOError(ENOENT, '%s not found' % (mode & X_OK and 'command' or 'file'), file)
    return path

if __name__ == '__main__':
    import doctest
    doctest.testmod()
