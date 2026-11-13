import json
from dataclasses import asdict, dataclass, field

from .catalog import ROUNDS, Card


STATUS_EFFECTS = ("Disarm", "Fracture", "Slow")
COUNTED_UPGRADES = ("speed", "strength")
UPGRADES = ("shield_active", "shield_spent", *COUNTED_UPGRADES)
SHIELD_SLOTS = 5
SHIELD_STATES = ("empty", "active", "spent")
UNIT_DEFEAT = "Unit defeat"
GARRISON_DEFEAT = "Garrison defeat"
GARRISON_RESCUE = "Garrison rescue"
GARRISON_POINTS = 2


def whole_number(value, label, minimum=None, maximum=None):
    try:
        if type(value) not in (int, str):
            raise ValueError
        number = int(value)
    except ValueError:
        raise ValueError(f"{label} must be a whole number.") from None
    if minimum is not None and number < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{label} must be at most {maximum}.")
    return number


def attack_damage(hits, modifier, active_shields):
    """Resolve table-adjusted damage before consuming only the Shields it reaches."""
    hits = whole_number(hits, "Hits", 0, 60)
    modifier = whole_number(modifier, "Damage modifier", -99, 99)
    active_shields = whole_number(active_shields, "Active Shields", 0)
    incoming = max(0, hits + modifier)
    blocked = min(incoming, active_shields)
    return blocked, incoming - blocked


@dataclass
class Unit:
    id: int
    player: int
    slot: int
    card: Card
    hp: int
    phase: int = 1
    round: int = 1
    stack: int = 0
    energy: int = 0
    deployed: bool = False
    statuses: list[str] = field(default_factory=list)
    shield_active: int = 0
    shield_spent: int = 0
    speed: int = 0
    strength: int = 0
    note: str = ""
    shield_slots: list[str] | None = None
    remote_weapon_hp: dict[str, int] = field(default_factory=dict)

    @property
    def label(self):
        return f"#{self.slot} {self.card.name}"

    @property
    def shields(self):
        if self.shield_slots is not None:
            return tuple(self.shield_slots)
        active = min(self.shield_active, SHIELD_SLOTS)
        spent = min(self.shield_spent, SHIELD_SLOTS - active)
        return ("active",) * active + ("spent",) * spent + ("empty",) * (SHIELD_SLOTS - active - spent)

    @property
    def extra_shields(self):
        return self.shield_active - self.shields.count("active"), self.shield_spent - self.shields.count("spent")


@dataclass
class ScoreEntry:
    player: int
    phase: int
    points: int
    reason: str


@dataclass
class Match:
    players: list[str]
    scenario: str
    phases: int
    units: list[Unit]
    phase: int = 1
    round: int = 1
    scores: list[ScoreEntry] = field(default_factory=list)
    winner: int | None = None
    scenario_id: str | None = None

    @classmethod
    def new(cls, players, scenario, phases, rosters, catalog, *, scenario_id=None):
        players = [player.strip() for player in players]
        if len(players) != 2 or not all(players):
            raise ValueError("Enter a name for both players.")
        phases = whole_number(phases, "Phase count", minimum=1)
        if len(rosters) != 2 or not all(rosters):
            raise ValueError("Add at least one published unit to each squad.")
        match = cls(players, scenario.strip(), phases, [], scenario_id=scenario_id)
        for player, roster in enumerate(rosters):
            added = set()
            for slot, card_number in enumerate(roster, 1):
                if card_number not in catalog:
                    raise ValueError(f"{card_number} is unavailable in the published catalog.")
                card = catalog[card_number]
                if not card.can_add_to(added):
                    raise ValueError(f"{card.name} [{card.number}] can only appear once in the same squad.")
                added.add(card_number)
                stack = len(match.tokens(player, 1, card.timeline))
                match.units.append(
                    Unit(len(match.units) + 1, player, slot, card, card.hp, round=card.timeline, stack=stack)
                )
        return match

    def to_json(self):
        payload = asdict(self)
        if self.scenario_id is None:
            del payload["scenario_id"]
        for unit in payload["units"]:
            if unit["shield_slots"] is None:
                del unit["shield_slots"]
            if not unit["remote_weapon_hp"]:
                del unit["remote_weapon_hp"]
            if not unit["card"]["mass_produced"]:
                del unit["card"]["mass_produced"]
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, payload):
        data = json.loads(payload)
        units = [Unit(**{**unit, "card": Card(**unit["card"])}) for unit in data.pop("units")]
        scores = [ScoreEntry(**score) for score in data.pop("scores")]
        return cls(**data, units=units, scores=scores)

    def unit(self, unit_id):
        return next(unit for unit in self.units if unit.id == unit_id)

    def tokens(self, player, phase, round_number):
        return sorted(
            (unit for unit in self.units if (unit.player, unit.phase, unit.round) == (player, phase, round_number)),
            key=lambda unit: unit.stack,
        )

    def set_cursor(self, phase, round_number):
        phase = whole_number(phase, "Phase", 1, self.phases)
        round_number = whole_number(round_number, "Round", 1, ROUNDS)
        self.phase, self.round = phase, round_number

    def adjacent_cursor(self, direction):
        index = (self.phase - 1) * ROUNDS + self.round - 1 + direction
        if 0 <= index < self.phases * ROUNDS:
            phase, round_number = divmod(index, ROUNDS)
            return phase + 1, round_number + 1
        return None

    def move_token(self, unit_id, phase, round_number, position=None):
        phase = whole_number(phase, "Scheduled Phase", 1)
        round_number = whole_number(round_number, "Scheduled round", 1, ROUNDS)
        unit = self.unit(unit_id)
        if position is None and (unit.phase, unit.round) == (phase, round_number):
            return
        destination = [token for token in self.tokens(unit.player, phase, round_number) if token.id != unit_id]
        last = len(destination) + 1
        position = last if position is None else whole_number(position, "Stack position", 1, last)
        destination.insert(position - 1, unit)
        unit.phase, unit.round = phase, round_number
        for stack, token in enumerate(destination):
            token.stack = stack

    def edit_unit(self, unit_id, *, hp, energy, deployed, statuses, note, upgrades,
                  shield_slots=None, keep_extra_shields=True):
        unit = self.unit(unit_id)
        hp = whole_number(hp, "HP", 0, unit.card.hp)
        energy = whole_number(energy, "Energy", 0)
        keys = UPGRADES if shield_slots is None else COUNTED_UPGRADES
        counts = {key: whole_number(upgrades[key], key.replace("_", " ").capitalize(), 0) for key in keys}
        if shield_slots is None:
            if (unit.shield_active, unit.shield_spent) != (counts["shield_active"], counts["shield_spent"]):
                unit.shield_slots = None
        else:
            if len(shield_slots) != SHIELD_SLOTS or any(state not in SHIELD_STATES for state in shield_slots):
                raise ValueError("Each of the five Shield tokens needs a valid state.")
            extra_active, extra_spent = unit.extra_shields if keep_extra_shields else (0, 0)
            counts["shield_active"] = shield_slots.count("active") + extra_active
            counts["shield_spent"] = shield_slots.count("spent") + extra_spent
            if tuple(shield_slots) != unit.shields:
                unit.shield_slots = list(shield_slots)
        unit.hp, unit.energy, unit.deployed = hp, energy, deployed
        if not deployed:
            unit.remote_weapon_hp.clear()
        unit.statuses = [status for status in STATUS_EFFECTS if status in statuses]
        unit.note = note.strip()
        for key, value in counts.items():
            setattr(unit, key, value)

    def clear_unit_status(self, unit_id, status):
        if self.winner is not None:
            return
        statuses = self.unit(unit_id).statuses
        if status in STATUS_EFFECTS and status in statuses:
            statuses.remove(status)

    def deploy_unit(self, unit_id):
        if self.winner is None:
            self.unit(unit_id).deployed = True

    def deploy_remote_weapon(self, unit_id, weapon):
        unit = self._remote_weapon_parent(unit_id, weapon)
        if unit.hp == 0:
            raise ValueError("The parent unit needs HP to deploy its Remote Weapon System.")
        unit.remote_weapon_hp.setdefault(weapon.number, weapon.hp)

    def adjust_remote_weapon_hp(self, unit_id, weapon, delta):
        unit = self._remote_weapon_parent(unit_id, weapon)
        hp = unit.remote_weapon_hp.get(weapon.number)
        if hp is None:
            return
        hp = min(weapon.hp, hp + whole_number(delta, "HP change"))
        if hp > 0:
            unit.remote_weapon_hp[weapon.number] = hp
            return
        self._return_defeated_remote_weapon(unit, weapon, self.phase)

    def defeat_remote_weapon(self, unit_id, weapon, scoring_phase, *, note=""):
        unit = self._remote_weapon_parent(unit_id, weapon)
        if weapon.number not in unit.remote_weapon_hp:
            raise ValueError("Choose a deployed Remote Weapon System. This system is in supply.")
        self._return_defeated_remote_weapon(unit, weapon, scoring_phase, note=note)

    def _return_defeated_remote_weapon(self, unit, weapon, scoring_phase, *, note=""):
        scoring_phase = whole_number(scoring_phase, "Scoring Phase", 1, self.phases)
        if weapon.vp:
            reason = f"RWS defeat · {weapon.name} · {unit.label}"
            if note := note.strip():
                reason += f" · {note}"
            self.scores.append(ScoreEntry(1 - unit.player, scoring_phase, weapon.vp, reason))
        del unit.remote_weapon_hp[weapon.number]

    def _remote_weapon_parent(self, unit_id, weapon):
        unit = self.unit(unit_id)
        if unit.card.number != weapon.parent:
            raise ValueError("Select the parent unit of this Remote Weapon System.")
        self._require_deployed_action(unit)
        return unit

    def energize_unit(self, unit_id):
        unit = self.unit(unit_id)
        self._require_deployed_action(unit)
        self._advance_token(unit, 2)
        unit.energy += 1

    def dash_unit(self, unit_id):
        unit = self.unit(unit_id)
        self._require_deployed_action(unit)
        self._advance_token(unit, 2)

    def resolve_attack(self, attacker_id, target_id, hits, *, modifier=0, note=""):
        """Apply one finalized weapon roll, including defeat, as one saved edit.

        Weapon/ability damage adjustments are adjudicated at the table before
        Shields. Range, line of sight and the attacker's Timeline cost remain manual.
        """
        try:
            attacker, target = self.unit(attacker_id), self.unit(target_id)
        except StopIteration:
            raise ValueError("Choose an attacker and target from this match.") from None
        self._require_deployed_action(attacker)
        self._require_deployed_action(target)
        if target.player == attacker.player:
            raise ValueError("Choose a deployed enemy unit as the target.")
        phase = whole_number(self.phase, "Scoring Phase", 1, self.phases)
        blocked, damage = attack_damage(hits, modifier, target.shield_active)
        for _ in range(blocked):
            self.adjust_shields(target, -1)
        defeated = damage > 0 and damage >= target.hp
        if defeated:
            self.defeat_unit(target_id, phase, note=note)
        elif damage:
            target.hp -= damage
        return defeated

    def defeat_unit(self, unit_id, scoring_phase, *, note="", defeated_weapons=()):
        unit = self.unit(unit_id)
        defeated_weapons = tuple(defeated_weapons)
        numbers = {weapon.number for weapon in defeated_weapons}
        if len(numbers) != len(defeated_weapons):
            raise ValueError("Each defeated Remote Weapon System can only be recorded once.")
        if numbers - unit.remote_weapon_hp.keys() or any(weapon.parent != unit.card.number for weapon in defeated_weapons):
            raise ValueError("Choose a deployed Remote Weapon System belonging to the defeated unit.")
        self._score_and_advance(unit, 1 - unit.player, scoring_phase, unit.card.vp, UNIT_DEFEAT, note)
        for weapon in defeated_weapons:
            self._return_defeated_remote_weapon(unit, weapon, scoring_phase)
        unit.deployed = False
        unit.hp = unit.card.hp
        unit.statuses.clear()
        unit.remote_weapon_hp.clear()

    def record_garrison(self, unit_id, scoring_phase, reason, *, note=""):
        if reason not in (GARRISON_DEFEAT, GARRISON_RESCUE):
            raise ValueError("Choose Garrison defeat or Garrison rescue.")
        unit = self.unit(unit_id)
        self._score_and_advance(unit, unit.player, scoring_phase, GARRISON_POINTS, reason, note)

    def _score_and_advance(self, unit, player, scoring_phase, points, reason, note):
        self._require_deployed_action(unit)
        scoring_phase = whole_number(scoring_phase, "Scoring Phase", 1, self.phases)
        reason = f"{reason} · {unit.label}"
        if note := note.strip():
            reason += f" · {note}"
        self._advance_token(unit, 2)
        self.scores.append(ScoreEntry(player, scoring_phase, points, reason))

    def _require_deployed_action(self, unit):
        if self.winner is not None:
            raise ValueError("The match is already complete.")
        if not unit.deployed:
            raise ValueError("Select a deployed unit. This unit is in Reserve.")

    def _advance_token(self, unit, spaces):
        phases_ahead, round_index = divmod(unit.round - 1 + spaces, ROUNDS)
        self.move_token(unit.id, unit.phase + phases_ahead, round_index + 1)

    def adjust_unit_counter(self, unit_id, counter, delta):
        if self.winner is not None:
            return
        unit = self.unit(unit_id)
        if counter == "shields":
            self.adjust_shields(unit, delta)
        elif counter in STATUS_EFFECTS:
            if delta > 0 and counter not in unit.statuses:
                unit.statuses = [status for status in STATUS_EFFECTS if status == counter or status in unit.statuses]
            elif delta < 0:
                self.clear_unit_status(unit_id, counter)
        elif counter in ("hp", "energy", *COUNTED_UPGRADES):
            value = max(0, getattr(unit, counter) + delta)
            setattr(unit, counter, min(value, unit.card.hp) if counter == "hp" else value)
        else:
            raise ValueError("Select a unit counter to adjust.")

    @staticmethod
    def adjust_shields(unit, delta):
        slots = list(unit.shields)
        if delta > 0:
            if unit.shield_spent:
                slots = ["active" if slot == "spent" else slot for slot in slots]
                unit.shield_active += unit.shield_spent
                unit.shield_spent = 0
            elif "empty" in slots and unit.shield_active < SHIELD_SLOTS:
                slots[slots.index("empty")] = "active"
                unit.shield_active += 1
            else:
                return
        elif delta < 0 and unit.shield_active:
            if "active" in slots:
                index = max(index for index, slot in enumerate(slots) if slot == "active")
                slots[index] = "spent"
            unit.shield_active -= 1
            unit.shield_spent += 1
        else:
            return
        unit.shield_slots = slots

    def record_score(self, player, phase, points, reason):
        if player not in (0, 1):
            raise ValueError("Select a scoring player.")
        phase = whole_number(phase, "Scoring Phase", 1, self.phases)
        points = whole_number(points, "VP")
        reason = reason.strip()
        if not points or not reason:
            raise ValueError("Enter a nonzero VP adjustment and its reason.")
        self.scores.append(ScoreEntry(player, phase, points, reason))

    def total(self, player):
        return sum(entry.points for entry in self.scores if entry.player == player)

    def finish(self, last_to_act=None):
        left, right = self.total(0), self.total(1)
        if left == right:
            if last_to_act not in (0, 1):
                raise ValueError("Select the player who acted last to break the tie.")
            self.winner = last_to_act
        else:
            self.winner = 0 if left > right else 1
