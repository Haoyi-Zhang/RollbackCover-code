from __future__ import annotations
import unittest, copy, json, itertools, tempfile
from pathlib import Path
from model import Model, horizon, no_duplicate_keys
from network import compile_network, lost_acknowledgements, hidden_reference_case, nonminimum_core_case, normalized, trace_set
from synthesis import Solver, extract_program, is_winning, minimal_core
from checker import check, check_core, InvalidCertificate
from oracle import oracle
from rr import execute_all, write_new


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.m=compile_network(0,('flip-x','read-x'));self.b=frozenset({1,3});self.k=2
        self.win=Solver(self.m).solve(self.b,2)
        self.lose=Solver(self.m).solve(self.b,1)

    def test_round_trip_model(self):
        self.assertEqual(self.m,Model.from_dict(json.loads(json.dumps(self.m.to_dict()))))

    def test_discriminating_scenario(self):
        self.assertEqual(check(self.m,self.b,2,self.win),'win')
        self.assertEqual(check(self.m,self.b,1,self.lose),'lose')
        runs=execute_all(self.m,self.b,2,extract_program(self.win))['runs']
        self.assertEqual(len(runs),2)
        self.assertTrue(all(r['final'] in self.m.goal for r in runs))

    def test_delete_observation_branch(self):
        c=copy.deepcopy(self.win);del c['branches']['1']
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_insert_spurious_observation(self):
        c=copy.deepcopy(self.win);c['branches']['invented']=c['branches']['0']
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_shrink_initial_belief(self):
        c=copy.deepcopy(self.win);c['belief']=[1]
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_shrink_successor_belief(self):
        c=copy.deepcopy(self.win);c['branches']['1']['belief']=[1]
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_wrong_rank(self):
        c=copy.deepcopy(self.win);c['rank']=3
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_bool_rank(self):
        c=copy.deepcopy(self.win);c['rank']=True
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_forged_stop(self):
        c={'kind':'win-stop','belief':[1,3],'rank':2}
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_wrong_action(self):
        c=copy.deepcopy(self.win);c['action']='flip-x'
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_missing_negative_action(self):
        c=copy.deepcopy(self.lose);del c['refusals']['flip-x']
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,1,c)

    def test_fake_disabled_witness(self):
        c=copy.deepcopy(self.lose);c['refusals']['flip-x']={'disabled':1}
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,1,c)

    def test_premature_timeout(self):
        c={'kind':'lose-horizon','belief':[1,3],'rank':2,'witness':3}
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_false_unsafe_witness(self):
        c={'kind':'lose-unsafe','belief':[1,3],'rank':2,'witness':1}
        with self.assertRaises(InvalidCertificate):check(self.m,self.b,2,c)

    def test_no_actions_and_deadlock(self):
        m=Model(('p','q'),(),(),frozenset({0,1}),frozenset({1}))
        c=Solver(m).solve(frozenset({0}),2)
        self.assertEqual(check(m,frozenset({0}),2,c),'lose')
        self.assertFalse(oracle(m,frozenset({0}),2)[0])

    def test_partially_disabled_action(self):
        m=Model(('p','q'),('a',),(((('o',1),),()),),frozenset({0,1}),frozenset({1}))
        self.assertFalse(is_winning(Solver(m).solve(frozenset({0,1}),1)))
        self.assertTrue(is_winning(Solver(m).solve(frozenset({0}),1)))
        forged={'kind':'win-step','rank':1,'belief':[0,1],'action':'a','branches':{'o':{'kind':'win-stop','rank':0,'belief':[1]}}}
        with self.assertRaises(InvalidCertificate):check(m,frozenset({0,1}),1,forged)

    def test_universal_safety_not_may_safety(self):
        m=Model(('p','goal','bad'),('a',),(((('o',1),('o',2)),(('o',1),),(('o',2),)),),frozenset({0,1}),frozenset({1}))
        self.assertFalse(is_winning(Solver(m).solve(frozenset({0}),1)))
        c={'kind':'win-step','belief':[0],'rank':1,'action':'a','branches':{'o':{'kind':'win-stop','belief':[1],'rank':0}}}
        with self.assertRaises(InvalidCertificate):check(m,frozenset({0}),1,c)

    def test_hidden_reference_correlation(self):
        m,b=hidden_reference_case()
        self.assertTrue(all(is_winning(Solver(m).solve(frozenset({w}),1)) for w in b))
        self.assertFalse(is_winning(Solver(m).solve(b,3)))
        self.assertFalse(oracle(m,b,2)[0])

    def test_minimal_is_not_minimum(self):
        m,b=nonminimum_core_case();packet=minimal_core(m,b,1);check_core(m,b,1,packet)
        self.assertEqual(packet['core'],[2,3,4])
        self.assertFalse(is_winning(Solver(m).solve(frozenset({0,1}),1)))
        self.assertTrue(all(is_winning(Solver(m).solve(frozenset({w}),1)) for w in b))

    def test_missing_deletion_witness(self):
        m,b=nonminimum_core_case();packet=minimal_core(m,b,1);del packet['deletions']['2']
        with self.assertRaises(InvalidCertificate):check_core(m,b,1,packet)

    def test_every_fault_position_and_stutter(self):
        cases=lost_acknowledgements(0,('set-y-1','set-x-1','set-x-1'))
        self.assertEqual([c['belief'] for c in cases],[[0,1],[1,3],[3]])
        self.assertEqual([c['position'] for c in cases],[0,1,2])

    def test_trace_identity_differs_from_projection(self):
        self.assertNotEqual(trace_set(0),trace_set(3))
        self.assertEqual(normalized(0,'erase-relay'),normalized(3,'erase-relay'))
        self.assertNotEqual(normalized(0,'erase-relay'),normalized(2,'erase-relay'))

    def test_inputs_reject_ill_formed_values(self):
        for k in [-1,33,True,0.5]:
            with self.assertRaises(ValueError):horizon(k)
        for b in [[],[1,1],[True],[4]]:
            with self.assertRaises(ValueError):self.m.belief(b)
        with self.assertRaises(ValueError):json.loads('{"a":1,"a":2}',object_pairs_hook=no_duplicate_keys)

    def test_unknown_model_keys_rejected(self):
        d=self.m.to_dict();d['instructions']='ignored'
        with self.assertRaises(ValueError):Model.from_dict(d)


    def test_strict_model_array_shapes(self):
        for malformed in [None, {}, 'ab', [0, 1], [['a', True]], [[['a', 1, 2]]]]:
            d = self.m.to_dict(); d['edges'] = [malformed]
            with self.assertRaises(ValueError):
                Model.from_dict(d)
        for key in ['worlds', 'actions', 'safe', 'goal']:
            d = self.m.to_dict(); d[key] = [{}]
            with self.assertRaises(ValueError):
                Model.from_dict(d)

    def test_boolean_certificate_belief_rejected(self):
        c = copy.deepcopy(self.win); c['belief'] = [True, 3]
        with self.assertRaises(InvalidCertificate):
            check(self.m, self.b, 2, c)

    def test_malformed_certificate_kind_rejected(self):
        c = copy.deepcopy(self.win); c['kind'] = []
        with self.assertRaises(InvalidCertificate):
            check(self.m, self.b, 2, c)

    def test_invalid_original_belief_in_core(self):
        m, b = nonminimum_core_case(); packet = minimal_core(m, b, 1)
        with self.assertRaises(ValueError):
            check_core(m, frozenset(set(b) | {500}), 1, packet)

    def test_interpreter_run_limit(self):
        with self.assertRaises(ValueError):
            execute_all(self.m, self.b, 2, extract_program(self.win), max_runs=1)

    def test_existential_reference_erasure_false_positive(self):
        m, b = hidden_reference_case()
        abstract = compile_network(0, m.actions)
        abstract = Model(abstract.worlds, abstract.actions, abstract.edges, abstract.safe,
                         frozenset(w % 4 for w in m.goal))
        self.assertTrue(is_winning(Solver(abstract).solve(frozenset({1}), 0)))
        self.assertFalse(is_winning(Solver(m).solve(b, 2)))

    def test_exclusive_and_bounded_publication(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'certificate.json'
            with self.assertRaises(ValueError):
                write_new(path, self.win, max_bytes=1)
            self.assertFalse(path.exists())
            write_new(path, self.win)
            original=path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_new(path, self.lose)
            self.assertEqual(path.read_bytes(), original)

if __name__=='__main__':unittest.main()


