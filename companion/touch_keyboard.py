"""Offline touch text entry shared by the four workspaces and their dialogs."""
import tkinter as tk
from tkinter import ttk

from .dialogs import Dialog
from .theme import AMBER, BORDER, CELL, INK, families

LETTERS = ('1234567890', 'qwertyuiop', "asdfghjkl'", 'zxcvbnm-._')
SYMBOLS = ('!@#$%^&*()', '[]{}<>/\\|=', ':;"?+_-.,~', '1234567890')


def keyboard_styles(root):
    heading, mono = families(root)
    style = ttk.Style(root)
    style.configure('InputKey.TButton', font=(mono, -20), padding=0, width=0)
    style.configure('InputEdit.TEntry', padding=(10, 10))
    style.configure('InputTitle.TLabel', font=(heading, -24, 'bold'), foreground=INK)
    for kind in ('Primary', 'Quiet'):
        style.configure(f'Input.{kind}.TButton', font=(heading, -17, 'bold'), padding=(16, 10))


class TextKeyboard(Dialog):
    def __init__(self, parent, variable, title, *, multiline=False, numeric=False,
                 allow_empty=True, trim=False, on_change=None, on_accept=None, source=None):
        super().__init__(parent, title)
        keyboard_styles(parent._root())
        self.target, self.source = variable, source
        self.original = variable.get()
        self.multiline, self.numeric = multiline, numeric
        self.allow_empty, self.trim = allow_empty, trim
        self.on_change, self.on_accept = on_change, on_accept
        self.shift = self.symbols = False
        self.value = tk.StringVar(self.window, self.original)
        self.root = parent._root()
        self.root.touch_keyboard = self
        heading, mono = families(parent)
        self.workspace.caption(self.body, title, 'InputTitle.TLabel').pack(anchor='w', pady=(0, 10))
        if multiline:
            editor = ttk.Frame(self.body, style='PanelFill.TFrame')
            editor.pack(fill='both', expand=True, pady=(0, 10))
            self.entry = tk.Text(editor, height=4, width=20, wrap='word', undo=True,
                background=CELL, foreground=INK, insertbackground=AMBER,
                highlightbackground=BORDER, highlightthickness=1, borderwidth=0,
                font=(heading, -18), padx=8, pady=6, exportselection=False)
            scroll = ttk.Scrollbar(editor, command=self.entry.yview)
            scroll.pack(side='right', fill='y')
            self.entry.pack(fill='both', expand=True)
            self.entry.configure(yscrollcommand=scroll.set)
            self.entry.insert('1.0', self.original)
            self.entry.mark_set('insert', 'end-1c')
            self.entry.see('insert')
            self.entry.edit_modified(False)
            self.entry.bind('<<Modified>>', self.text_changed)
        else:
            self.entry = ttk.Entry(self.body, textvariable=self.value, style='InputEdit.TEntry',
                font=(heading, -24, 'bold'), exportselection=False)
            self.entry.pack(fill='x', pady=(0, 12))
            self.entry.selection_range(0, 'end')
            self.entry.icursor('end')
        self.initial_focus = self.entry
        self.keys = ttk.Frame(self.body, style='PanelFill.TFrame')
        self.keys.pack(fill='x')
        self.buttons_by_key = {}
        self.build_keys()
        self.done = ttk.Button(self.footer, text='Done', style='Input.Primary.TButton', command=self.accept)
        self.done.pack(side='right')
        ttk.Button(self.footer, text='Cancel', style='Input.Quiet.TButton', command=self.cancel).pack(side='right', padx=(0, 10))
        self.trace = self.value.trace_add('write', self.refresh)
        self.window.bind('<Destroy>', self.cleanup, add='+')
        def finish(_event):
            self.accept()
            return 'break'
        self.entry.bind('<Control-Return>' if multiline else '<Return>', finish)
        self.refresh()
        self.show((540, 460) if numeric else (860, 590 if multiline else 510))

    @staticmethod
    def key(parent, text, command):
        return ttk.Button(parent, text=text, command=command, style='InputKey.TButton', takefocus=False)

    def build_keys(self):
        for child in self.keys.winfo_children():
            child.destroy()
        self.buttons_by_key.clear()
        rows = ('789', '456', '123', '-0+') if self.numeric else (SYMBOLS if self.symbols else LETTERS)
        for letters in rows:
            row = ttk.Frame(self.keys, style='PanelFill.TFrame')
            row.pack(fill='x', pady=3)
            row.columnconfigure(tuple(range(len(letters))), weight=1, uniform='keys')
            row.rowconfigure(0, minsize=48)
            for column, char in enumerate(letters):
                button = self.key(row, char.upper() if self.shift else char, lambda c=char: self.insert(c))
                button.grid(row=0, column=column, sticky='nsew', padx=3)
                self.buttons_by_key[char] = button
        bottom = ttk.Frame(self.keys, style='PanelFill.TFrame')
        bottom.pack(fill='x', pady=3)
        actions = [] if self.numeric else [('Shift', self.toggle_shift), ('ABC' if self.symbols else '#+=', self.toggle_symbols), ('Space', lambda: self.insert(' '))]
        if self.multiline:
            actions.append(('Enter', lambda: self.insert('\n')))
        actions.extend((('Backspace', self.backspace), ('Clear', self.clear)))
        bottom.columnconfigure(tuple(range(len(actions))), weight=1)
        bottom.rowconfigure(0, minsize=48)
        for column, (label, command) in enumerate(actions):
            button = self.key(bottom, label, command)
            button.grid(row=0, column=column, sticky='nsew', padx=3, ipadx=6)
            if label == 'Shift':
                self.shift_button = button
                button.state(['pressed'] if self.shift else ['!pressed'])

    def text_changed(self, _event=None):
        if self.entry.edit_modified():
            self.value.set(self.entry.get('1.0', 'end-1c'))
            self.entry.edit_modified(False)

    def delete_selection(self):
        selected = bool(self.entry.tag_ranges('sel')) if self.multiline else self.entry.selection_present()
        if selected:
            self.entry.delete('sel.first', 'sel.last')
        return selected

    def insert(self, character):
        self.delete_selection()
        self.entry.insert('insert', character.upper() if self.shift else character)
        if self.multiline:
            self.entry.see('insert')
            self.text_changed()
        self.entry.focus_set()

    def backspace(self):
        if not self.delete_selection():
            cursor = self.entry.index('insert')
            if self.multiline:
                if self.entry.compare(cursor, '>', '1.0'):
                    self.entry.delete('insert-1c', 'insert')
            elif cursor:
                self.entry.delete(cursor - 1, cursor)
        if self.multiline:
            self.text_changed()
        self.entry.focus_set()

    def clear(self):
        self.entry.delete('1.0' if self.multiline else 0, 'end')
        if self.multiline:
            self.text_changed()

    def toggle_shift(self):
        self.shift = not self.shift
        self.build_keys()

    def toggle_symbols(self):
        self.symbols = not self.symbols
        self.build_keys()

    def refresh(self, *_args):
        self.done.state(['!disabled'] if self.allow_empty or self.value.get().strip() else ['disabled'])
        if self.on_change is not None:
            self.on_change(self.value.get())

    def accept(self):
        if self.multiline:
            self.text_changed()
        text = self.value.get().strip() if self.trim else self.value.get()
        if self.allow_empty or text.strip():
            self.target.set(text)
            if self.on_accept is not None:
                self.on_accept(text)
            self.window.destroy()

    def cancel(self):
        if self.on_change is not None:
            self.on_change(self.original)
        super().cancel()

    def cleanup(self, event):
        if event.widget is self.window:
            self.value.trace_remove('write', self.trace)
            if getattr(self.root, 'touch_keyboard', None) is self:
                self.root.touch_keyboard = None


def bind_keyboard(widget, title, *, multiline=False, numeric=False, live=False):
    """Attach only to editable app fields, never read-only selectors or viewer text."""
    def read():
        return widget.get('1.0', 'end-1c') if multiline else widget.get()

    def write(text):
        if not widget.winfo_exists() or read() == text:
            return
        if multiline:
            separators = widget.cget('autoseparators')
            widget.edit_separator()
            widget.configure(autoseparators=False)
            try:
                widget.delete('1.0', 'end')
                widget.insert('1.0', text)
            finally:
                widget.configure(autoseparators=separators)
                widget.edit_separator()
        elif widget.cget('textvariable'):
            widget.tk.globalsetvar(widget.cget('textvariable'), text)
        else:
            widget.delete(0, 'end')
            widget.insert(0, text)

    def open_keyboard(event=None):
        if (str(widget.cget('state')) in ('disabled', 'readonly')
                or isinstance(widget, ttk.Widget) and (widget.instate(['disabled']) or widget.instate(['readonly']))):
            return
        if isinstance(widget, ttk.Spinbox) and event is not None and 'arrow' in widget.identify(event.x,event.y):
            return
        current = getattr(widget._root(), 'touch_keyboard', None)
        if current is not None and current.window.winfo_exists():
            current.window.lift()
            return
        buffer = tk.StringVar(widget, read())
        TextKeyboard(widget.winfo_toplevel(), buffer, title, multiline=multiline, numeric=numeric,
                     on_change=write if live else None, on_accept=write, source=widget)

    def destroyed(event):
        if event.widget is widget:
            current = getattr(widget._root(), 'touch_keyboard', None)
            if current is not None and current.source is widget and current.window.winfo_exists():
                current.cancel()

    widget.touch_keyboard_options = dict(title=title, multiline=multiline, numeric=numeric, live=live)
    widget.bind('<ButtonRelease-1>', open_keyboard, add='+')
    widget.bind('<Destroy>', destroyed, add='+')
    return widget
