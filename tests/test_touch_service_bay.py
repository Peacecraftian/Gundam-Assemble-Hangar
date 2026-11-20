import unittest
from companion.catalog import load_catalog
from companion.match import Match
from companion.touch_service import destination_positions


class ServiceBayPositionsTests(unittest.TestCase):
    def setUp(self):
        self.match = Match.new(['P1','P2'], '', 2,
                              [['PA01-U01','PA01-U02','PA01-U03'], ['ST01-U04','ST01-U05']], load_catalog())
        for unit in self.match.units:
            self.match.move_token(unit.id, 1, 4)

    def test_current_stack_highlights_existing_position(self):
        self.match.move_token(2,1,4,1)
        display, enabled, selected = destination_positions(self.match,self.match.unit(1),1,4)
        self.assertEqual(display,(1,2,3,4,5))
        self.assertEqual(enabled,(1,2,3))
        self.assertEqual(selected,2)

    def test_new_space_only_allows_real_insertion_positions(self):
        self.match.move_token(2,2,8)
        display, enabled, selected = destination_positions(self.match,self.match.unit(1),2,8)
        self.assertEqual(enabled,(1,2))
        self.assertEqual(selected,2)
        for rank in enabled:
            draft=Match.from_json(self.match.to_json())
            draft.move_token(1,2,8,rank)
            self.assertEqual(draft.tokens(0,2,8)[rank-1].id,1)

    def test_opponent_stack_does_not_create_allied_positions(self):
        self.match.move_token(4,2,8)
        self.match.move_token(5,2,8)
        _, enabled, selected=destination_positions(self.match,self.match.unit(1),2,8)
        self.assertEqual((enabled,selected),((1,),1))

    def test_future_phases_remain_available(self):
        self.match.move_token(1,4,10)
        _, enabled, selected=destination_positions(self.match,self.match.unit(1),4,10)
        self.assertEqual((enabled,selected),((1,),1))
        self.match.move_token(1,5,1,1)
        self.assertEqual(self.match.unit(1).phase,5)

if __name__=='__main__': unittest.main(verbosity=2)
