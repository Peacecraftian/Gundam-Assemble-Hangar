"""Status automation, based on Core Rulebook v1.2 (2026-11-06), pp. 28-29, 35, 37-38.

Shields resolve last: Fracture tests adjusted combat damage before Shields.
Disarm is explicitly resolved after other After Attack Roll abilities. Its token
is saved immediately after the mandatory reroll; applying damage is a separate edit.
"""
from tkinter import ttk
from . import dice_dialog
from .attacks import die_result, rifle_bonus
from .match import GARRISON
from .match import combat_damage, whole_number
from .touch_actions import TouchDiceTray, Stepper



def disarm_hits(values, accuracy, card_number=None):
    accuracy = whole_number(accuracy, 'Accuracy modifier', -99, 99)
    return tuple(i for i, value in enumerate(values) if die_result(value, accuracy, card_number) != 'miss')


def consume_disarm(match, attacker_id):
    match.consume_disarm(attacker_id)


def resolve_combat_attack(match, attacker_id, target_id, hits, *, timeline_cost=0, modifier=0, note='', weapon_bonus=0):
    try:
        target = match.attack_target(target_id)
    except StopIteration:
        raise ValueError('Choose an attacker and target from this match.') from None
    result = combat_damage(hits, modifier, target.shield_active, 'Fracture' in target.statuses, weapon_bonus)
    defeated = match.resolve_attack(attacker_id, target_id, hits, timeline_cost=timeline_cost, modifier=modifier, note=note, weapon_bonus=weapon_bonus)
    return defeated, result


class StatusDiceTray(TouchDiceTray):
    def __init__(self, parent, *args, **kwargs):
        attacker = kwargs.get('attacker')
        self.disarmed_attack = attacker is not None and 'Disarm' in attacker.statuses
        app = kwargs.get('app')
        declaration = app.match.pending_attack if app and attacker else None
        if declaration:
            self.disarmed_attack = declaration['disarmed']
        self.disarm_stage = ('resolved' if declaration and declaration['finalized'] else
                             'pending' if self.disarmed_attack else 'none')
        self.status_notice = None
        super().__init__(parent, *args, **kwargs)
        if declaration and declaration['values'] is not None:
            self.window.after_cancel(self.job)
            self.job = None
            self.values = tuple(declaration['values'])
            self.show_results()
        if self.attacker is not None:
            self.notice_box = ttk.Frame(self.body, style='Panel.TFrame', padding=(10, 6))
            self.notice_box.pack(fill='x', pady=(0, 6), before=self.canvas)
            self.status_notice = ttk.Label(self.notice_box, style='TouchScore.PanelMuted.TLabel', wraplength=1000)
            self.status_notice.pack(fill='x')
            def revise_labels(widget):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Label) and 'Resolve critical effects, Fracture' in str(child.cget('text')):
                        child.configure(text='Resolve other abilities at the table; Fracture and Shields are calculated automatically.')
                    revise_labels(child)
            revise_labels(self.body)
            self.refresh_notice()

    def refresh_notice(self):
        if self.status_notice is None:
            return
        if self.disarm_stage == 'pending':
            text = ('DISARM · Critical effects blocked for this attack. Finish other After Attack Roll abilities, '
                    'then tap Resolve Disarm to reroll every hit.')
        elif self.disarm_stage == 'rolling':
            text = 'DISARM · Rerolling all hits once. Misses stay unchanged; critical effects remain blocked.'
        elif self.disarm_stage == 'saving':
            text = 'DISARM · Reroll complete. Save Disarm to remove the status before applying damage.'
        elif self.disarm_stage == 'resolved':
            text = 'DISARM RESOLVED · Status removed. Critical effects remain blocked; attack dice are finalized.'
        elif self.target is not None and 'Fracture' in self.target.statuses:
            text = 'FRACTURE · 3+ combat damage before Shields adds 3 damage and consumes the status when applied.'
        else:
            text = ('TL paid · Attack reopens the saved roll. Undo takes back the declaration. '
                    'Resolve other weapon effects at the table.')
        self.status_notice.configure(text=text)

    def accuracy_controls(self):
        def find(widget):
            for child in widget.winfo_children():
                if isinstance(child, Stepper) and child.variable is self.accuracy:
                    yield child
                yield from find(child)
        return list(find(self.controls))

    def update_results(self, *_args):
        super().update_results(*_args)
        if self.state != 'results':
            return
        if self.disarmed_attack:
            # 9 and 10 are still automatic hits; only their critical effects are
            # suppressed, even after the Disarm token is removed.
            for item in self.canvas.find_withtag('result'):
                if self.canvas.type(item) == 'text':
                    text = self.canvas.itemcget(item, 'text')
                    if ' critical ' in text:
                        label = ' critical roll (effects blocked) ' if text.startswith('1 critical ') else ' critical rolls (effects blocked) '
                        self.canvas.itemconfigure(item, text=text.replace(' critical ', label))
            if self.disarm_stage in ('rolling', 'saving', 'resolved'):
                self.reroll_button.state(['disabled'])
                self.status.configure(text='Dice finalized.' if self.disarm_stage == 'resolved' else 'Resolving Disarm…')
                for stepper in self.accuracy_controls():
                    stepper.entry.state(['readonly'])
                    for _, button in stepper.buttons:
                        button.state(['disabled'])
            if self.app is not None and self.app.revision != self.revision:
                self.reroll_button.state(['disabled'])
        self.refresh_notice()

    def toggle_die(self):
        if self.disarm_stage not in ('rolling', 'saving', 'resolved'):
            super().toggle_die()

    def hover_die(self, event):
        if self.disarm_stage in ('rolling', 'saving', 'resolved'):
            self.canvas.configure(cursor='')
        else:
            super().hover_die(event)

    def reroll(self):
        if self.disarm_stage in ('rolling', 'saving', 'resolved'):
            return
        if self.app is not None and self.app.revision != self.revision:
            self.stale = True
            self.update_results()
            return
        super().reroll()

    def weapon_bonus(self):
        return rifle_bonus(self.attacker.card.number, self.weapon.name, self.values, self.disarmed_attack)

    def update_damage(self, hits):
        try:
            modifier = whole_number(self.damage_modifier.get(), 'Damage modifier', -99, 99)
            result = combat_damage(hits, modifier, self.target.shield_active, 'Fracture' in self.target.statuses, self.weapon_bonus())
        except ValueError as error:
            self.damage_summary.configure(text=str(error))
            return
        if self.app.revision != self.revision or self.stale:
            self.damage_summary.configure(text='The match changed. Close this roll and start a new attack.')
            return
        defeated = result.damage > 0 and result.damage >= self.target.hp
        outcome = (f'DEFEAT · +{self.target.card.vp} VP · Reserve / TL +2 / HP restored' if defeated and self.target is not GARRISON
                   else f'HP {self.target.hp} → {max(0, self.target.hp-result.damage)}')
        if self.target is GARRISON:
            outcome = '+2 VP · Remove Garrison' if defeated else 'Garrison remains'
        bonus = f' +{self.weapon_bonus()} rifle' if self.weapon_bonus() else ''
        fracture = ' +3 Fracture' if result.fracture_bonus else ''
        provisional = 'Before Disarm: ' if self.disarm_stage in ('pending', 'rolling') else ''
        self.damage_summary.configure(text=f'{provisional}{hits} hits {modifier:+d} modifier{bonus}{fracture}'
            f' − {result.blocked} Shields = {result.damage} damage · {outcome}')
        title = {'pending': 'Resolve Disarm', 'rolling': 'Resolving…', 'saving': 'Save Disarm'}.get(self.disarm_stage, 'Apply Damage')
        self.apply_button.configure(text=title)
        if not self.applying and not self.applied and self.disarm_stage != 'rolling':
            self.apply_button.state(['!disabled'])

    def begin_disarm(self):
        if self.disarm_stage != 'pending' or self.state != 'results':
            return
        try:
            indices = disarm_hits(self.values, self.accuracy.get(), self.attacker.card.number)
        except ValueError as error:
            self.error(str(error))
            return
        self.selected = set(indices)
        self.disarm_stage = 'rolling' if indices else 'saving'
        self.refresh_notice()
        if indices:
            self.reroll_indices = indices
            self.start()
        else:
            # No successful dice means there is nothing to reroll; this attack
            # still exhausts the next-attack status at the resolution checkpoint.
            self.finish_disarm()

    def reveal(self, rolled):
        mandatory = self.disarm_stage == 'rolling'
        super().reveal(rolled)
        if mandatory:
            self.disarm_stage = 'saving'
            self.finish_disarm()
        elif self.app and self.attacker and self.app.match.pending_attack:
            if self.app.revision == self.revision and self.app.edit(
                    lambda m: m.save_attack_roll(self.values, self.accuracy.get()), self.window):
                self.revision = self.app.revision
            else:
                self.stale = True
            self.update_results()

    def finish_disarm(self):
        if self.app.revision != self.revision:
            self.stale = True
            self.update_results()
            return
        def consume(match):
            if match.pending_attack:
                match.save_attack_roll(self.values, self.accuracy.get(), resolve_disarm=True)
            else:
                consume_disarm(match, self.attacker.id)
        if self.app.edit(consume, self.window):
            self.revision = self.app.revision
            self.attacker = self.app.match.unit(self.attacker.id)
            self.target = self.app.match.attack_target(self.target.id)
            self.disarm_stage = 'resolved'
            self.app.announce('●  Saved · Disarm resolved; critical effects blocked for this attack')
        self.update_results()

    def failed(self, error):
        if self.disarm_stage == 'rolling':
            self.disarm_stage = 'pending'
        super().failed(error)
        self.refresh_notice()

    def apply_damage(self):
        if self.state != 'results' or self.applying or self.applied or self.target is None:
            return
        if self.app.revision != self.revision or self.stale:
            self.stale = True
            self.update_results()
            return
        if self.disarm_stage == 'pending':
            self.begin_disarm()
            return
        if self.disarm_stage == 'saving':
            self.finish_disarm()
            return
        if self.disarm_stage == 'rolling':
            return
        try:
            hits = len(disarm_hits(self.values, self.accuracy.get(), self.attacker.card.number))
            modifier = whole_number(self.damage_modifier.get(), 'Damage modifier', -99, 99)
        except ValueError as error:
            self.error(str(error))
            return
        self.applying = True
        self.apply_button.state(['disabled'])
        outcome = []
        if not self.app.edit(lambda match: outcome.append(resolve_combat_attack(match,
                self.attacker.id, self.target.id, hits, timeline_cost=self.weapon.timeline, modifier=modifier,
                note=f'{self.attacker.label} / {self.weapon.name}', weapon_bonus=self.weapon_bonus())), self.window):
            self.applying = False
            if self.window.winfo_exists():
                self.update_results()
            return
        self.applied = True
        self.cancel()
        defeated, result = outcome[0]
        if defeated and self.target is GARRISON:
            self.app.announce('●  Saved · Enemy Garrison defeated · +2 VP')
            self.app.deployment.play_garrison(rescue=False, side=self.attacker.player, points=2)
        elif defeated:
            self.app.announce(f'●  Saved · {self.target.label} defeated · +{self.target.card.vp} VP')
            self.app.deployment.play_defeat()
        else:
            self.app.announce(f'●  Saved · {self.target.label} · {result.damage} HP damage'
                              + (' · Fracture consumed' if result.fracture_bonus else ''))
