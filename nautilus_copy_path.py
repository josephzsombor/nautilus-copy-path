import os
import json
import shlex
from urllib.parse import urlparse, unquote
from translation import Translation
from gi import require_version
import gi

require_version('Gtk', '3.0') #Changed to 3.0 to align with requirements of nautilus version on my Ubuntu 22.04 system
from gi.repository import Nautilus, GObject, Gtk, Gdk, GLib


class NautilusCopyPath(GObject.Object, Nautilus.MenuProvider):
    def _window_added(self, application, window):
        for key, shortcut_str in self.config["shortcuts"].items():
            if shortcut_str:
                action = Gtk.CallbackAction.new(self._shortcuts_handler)
                shortcut = Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(shortcut_str), action)
                shortcut.set_arguments(GLib.Variant.new_string(key))

                window.add_shortcut(shortcut)

    def _window_removed(self, application, window):
        window_id = window.get_id()
        if window_id in self.selected_files:
            del self.selected_files[window_id]

    def __init__(self):

        self.display = Gdk.Display.get_default()
#       self.clipboard = self.display.get_clipboard() #this wasn't working for me
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD) #changed to GTK 3 pattern
#       self.primary_clipboard = self.display.get_primary_clipboard() #this wasn't working for me
        self.primary_clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)

        self.selected_files = {}

        self.config = {
            "items": {
                "path": True,
                "uri": True,
                "name": True,
                "content": True
            },
            "selections": {
                "clipboard": True,
                "primary": True
            },
            "shortcuts": {
                "path": "<Ctrl><Shift>C",
                "uri": "<Ctrl><Shift>U",
                "name": "<Ctrl><Shift>D",
                "content": "<Ctrl><Shift>G"
            },
            "language": "auto",
            "separator": ", ",
            "escape_value_items": False,
            "escape_value": False,
            "name_ignore_extension": False
        }

        self.allow_copy_content = [
            "application/x-shellscript",
            "application/json",
        ]

        with open(os.path.join(os.path.dirname(__file__), "config.json")) as json_file:
            try:
                self.config.update(json.load(json_file))
                if self.config["language"]:
                    Translation.select_language(self.config["language"])
            except:
                pass

        app = Gtk.Application.get_default()
        app.connect("window-added", self._window_added)
        app.connect("window-removed", self._window_removed)

    def _shortcuts_handler(self, window, key):
        action = GLib.Variant.get_string(key)
        window_id = window.get_id()

        action_function = {
            'path': self._copy_paths,
            'uri': self._copy_uris,
            'name': self._copy_names,
            'content': self._copy_content
        }[action]

        if len(self.selected_files[window_id]) > 0 and action_function:
            action_function(None, self.selected_files[window_id])

    def get_file_items(self, *args):
        app = Gtk.Application.get_default()
        window = app.get_active_window()
        files = args[-1]

        self.selected_files[window.get_id()] = files

        return self._create_menu_items(files, "File")

    def get_background_items(self, *args):
        file = args[-1]
        return self._create_menu_items([file], "Background")

    def _create_menu_items(self, files, group):
        plural = len(files) > 1
        config_items = self.config["items"]
        active_items = []

        if config_items["path"]:
            item_path = Nautilus.MenuItem(
                name="NautilusCopyPath::CopyPath" + group,
                label=Translation.t("copy_paths" if plural else "copy_path"),
            )
            item_path.connect("activate", self._copy_paths, files)
            active_items.append(item_path)

        if config_items["uri"]:
            item_uri = Nautilus.MenuItem(
                name="NautilusCopyPath::CopyUri" + group,
                label=Translation.t("copy_uris" if plural else "copy_uri"),
            )
            item_uri.connect("activate", self._copy_uris, files)
            active_items.append(item_uri)

        if config_items["name"]:
            item_name = Nautilus.MenuItem(
                name="NautilusCopyPath::CopyName" + group,
                label=Translation.t("copy_names" if plural else "copy_name"),
            )
            item_name.connect("activate", self._copy_names, files)
            active_items.append(item_name)

        if config_items["content"]:
            filtered_files = []
            for file in files:
                file_type = file.get_mime_type()
                if file_type in self.allow_copy_content or file_type.startswith("text/"):
                    filtered_files.append(file)

            if len(filtered_files) > 0:
                item_name = Nautilus.MenuItem(
                    name="NautilusCopyPath::CopyContent" + group,
                    label=Translation.t("copy_content"),
                )
                item_name.connect("activate", self._copy_content, filtered_files)
                active_items.append(item_name)

        return active_items

    def _copy_paths(self, menu, files):
        def _uri_to_path(file):
            p = urlparse(file.get_activation_uri())
            return os.path.abspath(os.path.join(p.netloc, unquote(p.path)))

        self._copy_value(list(map(_uri_to_path, files)))

    def _copy_uris(self, menu, files):
        self._copy_value(list(map(lambda f: f.get_activation_uri(), files)))

    def _copy_names(self, menu, files):
        def _name(file):
            path = unquote(os.path.basename(file.get_activation_uri()))
            if self.config["name_ignore_extension"]:
                path = os.path.splitext(path)[0]

            return path

        self._copy_value(list(map(_name, files)))

    def _copy_content(self, menu, files):
        content = []
        for file in files:
            file_type = file.get_mime_type()
            if file_type in self.allow_copy_content or file_type.startswith("text/"):
                p = urlparse(file.get_activation_uri())
                p = os.path.abspath(os.path.join(p.netloc, unquote(p.path)))
                with open(p, 'r') as _file:
                    content.append(_file.read())

        self._copy_value(content)

    def _copy_value(self, value):
        if len(value) > 0:
            if self.config["escape_value_items"]:
                value = list(map(lambda x: shlex.quote(x), value))

            new_value = self.config["separator"].join(value)

            if self.config["escape_value"]:
                new_value = shlex.quote(new_value)

            if self.config["selections"]["clipboard"]:
#               self.clipboard.set(new_value) #wasn't working for me
                self.clipboard.set_text(new_value, -1) #changed to GTK 3 pattern
                self.clipboard.store()

            if self.config["selections"]["primary"]:
#               self.primary_clipboard.set(new_value) #wasn't working for me
                self.primary_clipboard.set_text(new_value, -1) #changed to GTK 3 pattern
                self.primary_clipboard.store()
