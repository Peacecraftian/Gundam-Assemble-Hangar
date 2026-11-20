"""Mission Sortie touch styling and an offline player-name keyboard."""
from tkinter import ttk

from .theme import families
from .touch_keyboard import TextKeyboard


def setup_sortie_styles(root):
    heading, mono = families(root)
    style = ttk.Style(root)
    style.configure('TouchSortie.Catalog.Treeview', rowheight=64, font=(heading, -16, 'bold'))
    style.layout('TouchSortie.Catalog.Treeview.Item', style.layout('Catalog.Treeview.Item'))
    style.configure('TouchSortie.RosterRow.TLabel', font=(heading, -16, 'bold'))
    style.configure('TouchSortie.WellMeta.TLabel', font=(mono, -11))
    style.configure('TouchSortie.Icon.TButton', font=(mono, -24), padding=0, width=0)
    style.configure('TouchSortie.Sortie.TEntry', padding=(10, 10))
    style.configure('TouchSortie.Step.TEntry', padding=(4, 9))
    style.configure('TouchSortie.TCombobox', padding=(8, 9), arrowsize=22)
    style.configure('TouchSortie.Vertical.TScrollbar', arrowsize=24)
    for side in range(2):
        style.configure(f'TouchSortie.Name{side}.TEntry', padding=(5, 10))
        style.configure(f'TouchSortie.Edit{side}.Icon.TButton', font=(heading, -22), padding=(10, 6))
        style.configure(f'TouchSortie.Side{side}.TButton', font=(heading, -16, 'bold'), padding=(8, 12))
    for kind in ('Primary', 'Quiet'):
        style.configure(f'TouchSortie.{kind}.TButton', font=(heading, -17, 'bold'), padding=(16, 10))


class PlayerNameKeyboard(TextKeyboard):
    def __init__(self, parent, variable, side):
        super().__init__(parent, variable, f'Player {side + 1} Name', allow_empty=False, trim=True)
