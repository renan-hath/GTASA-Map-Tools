"""
Finds the limit adjusters of a GTA San Andreas folder (fastman92 Limit Adjuster, Open Limit
Adjuster and this tool's $$MapLimits.asi) and reads and changes their INI files, keeping the
rest of each file as it is.
"""
import os
import re

UNLIMITED = 1 << 31


class IniFile:
    """
    An INI file whose settings can be read and changed line by line. A setting that is turned
    off starts with the inactive prefix ('#' in fastman92's file, ';' in Open Limit Adjuster's).
    """

    def __init__(self, path, inactive_prefix):
        self.path = path
        self.inactive_prefix = inactive_prefix

        with open(path, 'rb') as ini_file:
            content = ini_file.read().decode('latin-1')

        self.newline = '\r\n' if '\r\n' in content else '\n'
        self.lines = content.split(self.newline)
        self.changed = False

    def _setting_pattern(self, key, inactive):
        prefix = rf'\s*{re.escape(self.inactive_prefix)}\s*' if inactive else r'\s*'
        return re.compile(rf'^{prefix}({re.escape(key)})\s*=\s*([^;#\t]*)', re.IGNORECASE)

    def _section_range(self, section):
        # The lines of a section, or of the whole file without one
        if section is None:
            return 0, len(self.lines)

        start = None

        for index, line in enumerate(self.lines):
            text = line.strip()

            if text.startswith('['):
                if start is not None:
                    return start, index

                if text[1:text.find(']')].strip().lower() == section.lower():
                    start = index + 1

        return (start, len(self.lines)) if start is not None else (None, None)

    def find(self, key, section=None, inactive=False):
        """Returns the index of the line that sets the key and its value, or None and None."""
        start, end = self._section_range(section)

        if start is None:
            return None, None

        pattern = self._setting_pattern(key, inactive)

        for index in range(start, end):
            match = pattern.match(self.lines[index])

            if match:
                return index, match.group(2).strip()

        return None, None

    def get(self, key, section=None):
        """Returns the value of a setting that is on, or None."""
        return self.find(key, section)[1]

    def get_number(self, key, section=None):
        value = self.get(key, section)

        if value is None:
            return None

        if value.lower() == 'unlimited':
            return UNLIMITED

        try:
            return int(float(value))
        except ValueError:
            return None

    def set(self, key, value, section):
        """Sets a setting, turning it on if it is off, or adding it to its section."""
        line = f'{key} = {value}'
        index, _ = self.find(key, section)

        if index is None:
            index, _ = self.find(key, section, inactive=True)

        if index is not None:
            indent = re.match(r'^\s*', self.lines[index]).group(0)
            self.lines[index] = indent + line
        else:
            start, _ = self._section_range(section)

            if start is None:
                while self.lines and not self.lines[-1].strip():
                    self.lines.pop()

                self.lines += ['', f'[{section}]', line, '']
            else:
                self.lines.insert(start, line)

        self.changed = True

    def turn_off(self, key, section=None):
        index, _ = self.find(key, section)

        if index is not None:
            self.lines[index] = self.inactive_prefix + self.lines[index].lstrip()
            self.changed = True

    def save(self):
        with open(self.path, 'wb') as ini_file:
            ini_file.write(self.newline.join(self.lines).encode('latin-1'))

        self.changed = False


class LimitAdjusters:
    """The limit adjusters installed in a game folder."""

    FLA_INI_NAME = 'fastman92limitAdjuster_GTASA.ini'
    FLA_ASI_PATTERN = re.compile(r'^.*fastman92limitadjuster.*\.asi$', re.IGNORECASE)
    OLA_INI_NAME = 'III.VC.SA.LimitAdjuster.ini'
    OLA_ASI_NAME = 'III.VC.SA.LimitAdjuster.asi'
    OLA_SECTION = 'SALIMITS'
    MAP_LIMITS_ASI_NAME = '$$MapLimits.asi'

    def __init__(self, game_dir):
        self.game_dir = game_dir or ''
        self.fla = None
        self.ola = None
        self.fla_asi = ''
        self.ola_asi = ''
        self.map_limits_asi = ''

        if not os.path.isdir(self.game_dir):
            return

        fla_ini = self._find(self.FLA_INI_NAME, [(self.game_dir, 0)])

        if fla_ini:
            self.fla = IniFile(fla_ini, '#')

        # Open Limit Adjuster is looked for where MapLimits looks for it
        places = [(self.game_dir, 0), (os.path.join(self.game_dir, 'modloader'), 4),
                  (os.path.join(self.game_dir, 'scripts'), 1)]
        ola_ini = self._find(self.OLA_INI_NAME, places)

        if ola_ini:
            self.ola = IniFile(ola_ini, ';')

        self.fla_asi = self._find(self.FLA_ASI_PATTERN, [(self.game_dir, 0), (os.path.join(self.game_dir, 'scripts'), 0)])
        self.ola_asi = self._find(self.OLA_ASI_NAME, places)
        self.map_limits_asi = self._find(self.MAP_LIMITS_ASI_NAME, [(self.game_dir, 0)])

    @staticmethod
    def _find(name, places):
        # The first file with that name (or matching that pattern) in each place and the folders
        # inside it up to a depth, skipping the ones modloader ignores
        for directory, depth in places:
            if not os.path.isdir(directory):
                continue

            pending = [(directory, depth)]

            while pending:
                current, current_depth = pending.pop(0)

                try:
                    entries = sorted(os.scandir(current), key=lambda entry: entry.name.lower())
                except OSError:
                    continue

                for entry in entries:
                    if entry.is_file():
                        matches = (name.match(entry.name) if hasattr(name, 'match')
                                   else entry.name.lower() == name.lower())

                        if matches:
                            return entry.path
                    elif entry.is_dir() and current_depth > 0 and not entry.name.startswith('.'):
                        pending.append((entry.path, current_depth - 1))

        return ''

    @property
    def has_fla(self):
        return self.fla is not None

    @property
    def has_ola(self):
        return self.ola is not None

    def get_fla(self, key, default=0):
        """Returns the value fastman92's INI sets for a key, and whether it sets it."""
        value = self.fla.get_number(key) if self.fla else None
        return (default, False) if value is None else (value, True)

    def get_fla_size(self, key):
        # A map size fastman92's INI sets, or 0
        return self.get_fla(key, 0)[0]
