"""Read-only historical execution. No Tk GUI, no bytecode in evidence.
These tests capture old behaviour BEFORE maintained safety corrections.
"""
import collections
from pathlib import Path
import types

ROOT = Path(__file__).parents[1] / 'old_evidence/tkinter-version/src/core/logic'

class Var:
    def set(self, value): self.value = value
    def get(self): return getattr(self, 'value', '')

def legacy_file(path, dependencies=None):
    source = (ROOT / path).read_text()
    source = '\n'.join(line for line in source.splitlines() if not line.startswith('from core.'))
    scope = dict(dependencies or {})
    exec(compile(source, str(ROOT / path), 'exec'), scope)
    return scope

def section():
    return types.SimpleNamespace(vars=collections.defaultdict(Var))

def test_legacy_full_half_bead_and_ledge():
    packing = legacy_file('shared/layout_strips.py')
    s = section()
    legacy_file('full_wall/calc_full_wall.py', packing)['calc_square_full'](s,3000,2400,4,2,100,2440,3)
    assert (s.vars['square_width_var'].get(),s.vars['square_height_var'].get()) == ('625.0','1050.0')
    assert [len(s.square_strip_cut_list[g]) for g in ['vertical','horizontal']] == [5,4]
    legacy_file('half_wall/calc_half_wall.py', packing)['calc_square_half'](s,3000,1000,4,1,100,2440,3)
    assert [len(s.half_square_strip_cut_list[g]) for g in ['vertical','top_and_bottom_horizontal']] == [2,3]
    legacy_file('half_wall/calc_half_ledge.py', packing)['calc_ledge_half'](s,3000,2440,3)
    assert len(s.ledge_cut_list) == 2
    legacy_file('shared/bead_calculations.py', packing)['generate_bead_cut_list'](s,625,800,4,2400,'Half Wall with Ledge & Bead',3000,3)
    assert s.vars['bead_strips_var'].get() == '8'

def test_legacy_stair_golden_and_bead():
    packing = legacy_file('shared/layout_strips.py')
    s = section()
    legacy_file('half_wall/calc_half_stairs.py', packing)['calc_stair_half'](s,1500,1000,250,250,1200,4,1,100,2440,3)
    assert [x['type'] for x in s.square_layout] == ['transition','angled','angled','transition']
    expected={'square_width_var':'250.0','square_height_var':'800.0','angled_square_width_var':'300.0','angled_square_height_var':'960.0','slope_mitre_var':'16.78°','angled_square_mitres_var':'61.78° (T) / 28.22° (B)','horz_strips_var':'2','vert_strips_var':'3'}
    assert {k:s.vars[k].get() for k in expected} == expected
    legacy_file('shared/bead_calculations.py', packing)['generate_bead_cut_list_stair'](s,(250,800,0),(300,960,4),2400,'bead',1500,3)
    assert sum(len(v) for v in s.vars['bead_cut_list'].values()) > 0

def test_legacy_packing_defects_are_characterized():
    pack = legacy_file('shared/layout_strips.py')['layout_strips']
    assert len(pack([500,497],1000,3)) == 2  # contradictory placement kerf
    assert pack([3500],3000,3)['Strip 1']['used'] == 3500  # unsafe singleton
