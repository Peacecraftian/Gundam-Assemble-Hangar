import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from companion.artwork import PhotoCache
from companion.catalog import load_catalog
from companion.attacks import load_attacks
from companion.match import Match
from companion.storage import MatchStore
from companion.theme import setup_theme
from companion.status_rules import combat_damage, consume_disarm, disarm_hits, resolve_combat_attack, StatusDiceTray


class StatusRulesTests(unittest.TestCase):
    def setUp(self):
        self.catalog=load_catalog()
        self.match=Match.new(['Blue','Red'],'',2,[['PA01-U01'],['ST01-U04']],self.catalog)
        self.match.deploy_unit(1)
        self.match.deploy_unit(2)
        self.attacker,self.target=self.match.units

    def test_fracture_threshold_precedes_shields_and_consumes_when_fully_blocked(self):
        for hits,modifier,shields,bonus,blocked,damage in (
            (2,0,0,0,0,2),(3,0,0,3,0,6),(3,0,4,3,4,2),
            (3,0,7,3,6,0),(4,-2,0,0,0,2),(2,1,1,3,1,5),
            (60,99,0,3,0,162)):
            with self.subTest(hits=hits,modifier=modifier,shields=shields):
                r=combat_damage(hits,modifier,shields,True)
                self.assertEqual((r.fracture_bonus,r.blocked,r.damage),(bonus,blocked,damage))
        self.target.statuses=['Fracture','Slow']
        self.target.shield_active=7
        hp=self.target.hp
        defeated,result=resolve_combat_attack(self.match,1,2,3)
        self.assertFalse(defeated)
        self.assertEqual(self.target.hp,hp)
        self.assertEqual(self.target.statuses,['Slow'])
        self.assertEqual((self.target.shield_active,self.target.shield_spent),(1,6))

    def test_nontriggering_attack_and_direct_hp_edits_preserve_fracture(self):
        self.target.statuses=['Fracture']
        resolve_combat_attack(self.match,1,2,2)
        self.assertEqual(self.target.statuses,['Fracture'])
        self.target.hp-=4  # same independent HP adjustment path, no attack resolver
        self.assertEqual(self.target.statuses,['Fracture'])

    def test_damage_defeat_save_and_undo_are_atomic(self):
        self.target.statuses=['Fracture','Slow']
        self.target.hp=5
        self.target.energy=3
        self.target.strength=2
        self.target.shield_active=1
        before=self.match.to_json()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'match.sqlite3'
            store=MatchStore(path)
            revision=store.save(self.match,0)
            defeated,result=resolve_combat_attack(self.match,1,2,3)
            self.assertTrue(defeated)
            self.assertEqual(result.damage,5)
            self.assertEqual(self.target.statuses,[])
            self.assertEqual((self.target.deployed,self.target.hp),(False,self.target.card.hp))
            self.assertEqual((self.target.energy,self.target.strength),(3,2))
            self.assertEqual(self.match.total(0),self.target.card.vp)
            store.save(self.match,revision)
            store.close()
            store=MatchStore(path)
            loaded,revision=store.load()
            restored,_=store.undo(revision)
            self.assertEqual(restored.to_json(),before)
            store.close()

    def test_disarm_rerolls_criticals_and_accuracy_hits_but_preserves_misses(self):
        self.assertEqual(disarm_hits((1,2,3,4,8,9,10),1),(2,3,4,5,6))
        self.assertEqual(disarm_hits((1,2,3,4,8,9,10),-5),(5,6))
        self.assertEqual(disarm_hits((),0),())

    def test_slow_never_blocks_timeline_or_dash_and_other_statuses_remain(self):
        self.attacker.statuses=['Slow','Disarm','Fracture']
        before=self.attacker.round
        self.match.dash_unit(1)
        self.assertEqual(self.attacker.round,before+2)
        self.assertEqual(self.attacker.statuses,['Slow','Disarm','Fracture'])
        self.match.energize_unit(1)
        self.match.move_token(1,2,8)
        self.assertEqual(self.attacker.statuses,['Slow','Disarm','Fracture'])
        consume_disarm(self.match,1)
        self.assertEqual(self.attacker.statuses,['Slow','Fracture'])

    def test_invalid_attacks_do_not_consume_statuses(self):
        self.target.statuses=['Fracture']
        for attacker,target,hits,modifier in ((1,1,4,0),(1,2,61,0),(1,2,3,'bad'),(99,2,3,0)):
            before=self.match.to_json()
            with self.assertRaises(ValueError):
                resolve_combat_attack(self.match,attacker,target,hits,modifier=modifier)
            self.assertEqual(self.match.to_json(),before)
        self.attacker.statuses=['Disarm']
        with self.assertRaisesRegex(ValueError,'Disarm'):
            resolve_combat_attack(self.match,1,2,3)


class StatusTrayTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Native Tk display unavailable: {error}")
        self.root.withdraw()
        setup_theme(self.root)
        self.tmp=tempfile.TemporaryDirectory()
        self.store=MatchStore(Path(self.tmp.name)/'match.sqlite3')
        catalog=load_catalog()
        match=Match.new(['Blue','Red'],'',2,[['PA01-U01'],['ST01-U04']],catalog)
        match.deploy_unit(1)
        match.deploy_unit(2)
        match.unit(1).statuses=['Disarm','Slow']
        match.unit(2).statuses=['Fracture']
        revision=self.store.save(match,0)
        self.before=match.to_json()
        self.app=SimpleNamespace(root=self.root,match=match,revision=revision,photos=PhotoCache(self.root),
                                 deployment=Mock(),announce=Mock())
        def edit(action,parent):
            draft=Match.from_json(self.app.match.to_json())
            action(draft)
            self.app.revision=self.store.save(draft,self.app.revision)
            self.app.match=draft
            return True
        self.app.edit=edit
        self.show=patch('companion.dialogs.Dialog.show')
        self.show.start()
        self.start=patch.object(StatusDiceTray,'start')
        self.start.start()
        self.tray=StatusDiceTray(self.root,'Test Attack',4,0,0,app=self.app,attacker=match.unit(1),
            target=match.unit(2),weapon=load_attacks(catalog)['PA01-U01'][0],revision=revision)
        self.root.update_idletasks()
        self.tray.error=Mock()

    def tearDown(self):
        self.start.stop()
        self.show.stop()
        self.root.destroy()
        self.store.close()
        self.tmp.cleanup()

    def test_declared_garrison_attack_resumes_after_disarm_and_undo_restores_actor(self):
        from companion.match import GARRISON
        self.tray.cancel()
        weapon = load_attacks(load_catalog())['PA01-U01'][0]
        self.app.edit(lambda m: m.declare_attack(1, 0, weapon, 2, 0), self.root)
        paid = self.app.match.unit(1).round
        self.assertEqual(paid, self.app.match.unit(1).card.timeline + weapon.timeline)
        def reopen():
            return StatusDiceTray(self.root, 'Garrison attack', 2, 0, 0, app=self.app,
                                  attacker=self.app.match.unit(1), target=GARRISON, weapon=weapon,
                                  revision=self.app.revision)
        t = reopen()
        t.reveal((9, 1))
        t.apply_damage()
        t.reveal((5,))
        t.cancel()
        t = reopen()
        self.assertEqual((t.values, t.disarm_stage), ((5, 1), 'resolved'))
        t.apply_damage()
        self.assertEqual((self.app.match.unit(1).round, self.app.match.total(0)), (paid, 2))
        self.app.deployment.play_garrison.assert_called_once_with(rescue=False, side=0, points=2)
        self.assertEqual(self.store.undo(self.app.revision)[0].to_json(), self.before)

    def test_mandatory_reroll_is_once_then_consumed_and_persisted(self):
        t=self.tray
        t.reveal((1,4,9,10))
        t.apply_damage()
        self.assertEqual(t.reroll_indices,(1,2,3))
        self.assertEqual(t.disarm_stage,'rolling')
        self.assertIn('Disarm',self.app.match.unit(1).statuses)
        t.reveal((2,9,4))
        self.assertEqual(t.values,(1,2,9,4))
        self.assertEqual(t.disarm_stage,'resolved')
        self.assertEqual(self.app.match.unit(1).statuses,['Slow'])
        self.assertEqual(self.store.load()[0].unit(1).statuses,['Slow'])
        self.assertEqual(t.revision,self.app.revision)
        self.assertTrue(t.disarmed_attack)
        self.assertTrue(t.reroll_button.instate(['disabled']))
        t.selected={2}
        t.reroll()
        self.assertEqual(t.reroll_indices,())
        captions=[t.canvas.itemcget(i,'text') for i in t.canvas.find_withtag('result') if t.canvas.type(i)=='text']
        self.assertTrue(any('effects blocked' in text for text in captions))
        start_round=t.attacker.card.timeline
        self.assertEqual(self.app.match.unit(1).round,start_round)
        target_hp=self.app.match.unit(2).hp
        t.apply_damage()
        t.apply_damage()  # Ignore a second tap on this finalized roll.
        self.assertEqual(self.app.match.unit(1).round,start_round+t.weapon.timeline)
        self.assertEqual(self.app.match.unit(2).hp,target_hp-2)
        self.assertIn('Fracture',self.app.match.unit(2).statuses)
        restored,rev=self.store.undo(self.app.revision)
        self.assertNotIn('Disarm',restored.unit(1).statuses)
        restored,rev=self.store.undo(rev)
        self.assertEqual(restored.to_json(),self.before)

    def test_no_hits_or_zero_pool_still_consumes_at_resolution_checkpoint(self):
        self.tray.reveal((1,2,3,1))
        self.tray.apply_damage()
        self.assertEqual(self.tray.disarm_stage,'resolved')
        self.assertNotIn('Disarm',self.app.match.unit(1).statuses)
        self.assertEqual(self.tray.values,(1,2,3,1))
        prepared=self.app.match.to_json()
        self.tray.apply_damage()
        self.assertEqual(self.app.match.unit(1).round,self.tray.attacker.card.timeline+self.tray.weapon.timeline)
        restored,_=self.store.undo(self.app.revision)
        self.assertEqual(restored.to_json(),prepared)

    def test_zero_dice_resolves_without_starting_another_roll(self):
        self.tray.count=0
        self.tray.reveal(())
        self.tray.apply_damage()
        self.assertEqual(self.tray.disarm_stage,'resolved')
        self.assertNotIn('Disarm',self.app.match.unit(1).statuses)

    def test_post_disarm_fracture_preview_matches_saved_damage(self):
        self.app.match.unit(2).shield_active=1
        self.tray.reveal((1,4,9,10))
        self.tray.apply_damage()
        self.tray.reveal((4,9,10))
        self.assertIn('+3 Fracture',self.tray.damage_summary.cget('text'))
        self.assertIn('5 damage',self.tray.damage_summary.cget('text'))
        before=self.app.match.unit(2).hp
        self.tray.apply_damage()
        self.assertEqual(self.app.match.unit(2).hp,before-5)
        self.assertNotIn('Fracture',self.app.match.unit(2).statuses)
        self.assertEqual(self.app.match.unit(2).shield_active,0)

    def test_cancel_before_disarm_keeps_status(self):
        self.tray.reveal((1,4,9,10))
        self.tray.cancel()
        self.assertEqual(self.store.load()[0].to_json(),self.before)

    def test_stale_revision_blocks_reroll_and_damage(self):
        self.tray.reveal((1,4,9,10))
        self.app.revision+=1
        self.tray.apply_damage()
        self.assertEqual(self.tray.disarm_stage,'pending')
        self.assertTrue(self.tray.stale)
        self.assertEqual(self.store.load()[0].to_json(),self.before)

    def test_save_failure_retries_consumption_without_rerolling(self):
        self.tray.reveal((1,4,9,10))
        self.tray.apply_damage()
        original=self.app.edit
        self.app.edit=Mock(return_value=False)
        self.tray.reveal((1,2,9))
        self.assertEqual(self.tray.disarm_stage,'saving')
        self.assertIn('Disarm',self.app.match.unit(1).statuses)
        values=self.tray.values
        self.app.edit=original
        self.tray.apply_damage()
        self.assertEqual(self.tray.disarm_stage,'resolved')
        self.assertEqual(self.tray.values,values)

    def test_failed_dice_engine_does_not_consume_disarm(self):
        self.tray.reveal((1,4,9,10))
        self.tray.apply_damage()
        self.tray.failed(RuntimeError('test failure'))
        self.assertEqual(self.tray.disarm_stage,'pending')
        self.assertIn('Disarm',self.app.match.unit(1).statuses)
        self.assertEqual(self.tray.values,(1,4,9,10))

if __name__=='__main__':
    unittest.main()
