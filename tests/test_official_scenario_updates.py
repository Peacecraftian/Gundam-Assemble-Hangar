"""Verify newly bundled boards against their preserved authoring exports."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from companion.scenarios import load_scenarios,read_scenario_file,scenario_choices
from companion.storage import MatchStore

ROOT=Path(__file__).resolve().parents[1]


class OfficialScenarioUpdateTests(unittest.TestCase):
    def test_gravedigger_preserves_complete_authoring_scenario(self):
        official=next(s for s in load_scenarios(ROOT) if s['id']=='official-gravedigger')
        source=read_scenario_file(ROOT/official['source'])
        self.assertEqual({key:official[key] for key in source},source)
        self.assertEqual(official['palette'],'space')
        for token,count in (('objective',3),('special_objective',2)):
            numbers=sorted(c['objective_number'] for c in official['cells'].values() if c.get('token')==token)
            self.assertEqual(numbers,list(range(1,count+1)))

    def test_azure_restores_only_two_deployment_hexes_and_keeps_identity(self):
        official=next(s for s in load_scenarios(ROOT) if s['id']=='official-azure-fang')
        before=read_scenario_file(ROOT/'authoring/scenarios/export-official-azure-fang-rev2.json')
        after=read_scenario_file(ROOT/official['source'])
        self.assertEqual(official['name'],'Operation Azure Fang')
        for key in ('location','overview','objectives','palette'):
            self.assertEqual(official[key],before[key])
        self.assertEqual(official['cells'],after['cells'])
        changed={key for key in before['cells'] if before['cells'][key]!=official['cells'][key]}
        self.assertEqual(changed,{'01-08','13-08'})
        self.assertEqual(official['cells']['01-08'],{'terrain':'height1','token':'red_base'})
        self.assertEqual(official['cells']['13-08'],{'terrain':'height1','token':'blue_base'})

    def test_shared_selectors_expose_official_entries_with_deletion_protection(self):
        with TemporaryDirectory() as folder:
            store=MatchStore(Path(folder)/'review.sqlite3')
            try:
                choices,labels=scenario_choices(store)
                for identifier in ('official-gravedigger','official-azure-fang'):
                    position=next(i for i,(s,_) in enumerate(choices) if s['id']==identifier)
                    scenario,revision=choices[position]
                    self.assertEqual(revision,0)
                    self.assertEqual(labels[position],scenario['name'])
                    with self.assertRaises(ValueError):
                        store.delete_scenario(identifier,revision)
            finally:
                store.close()
