import json
from pathlib import Path
from scripts.inspect_backlog import inspect

def test_dev_beads_graph_valid_and_large():
    data=json.loads((Path(__file__).resolve().parent.parent/'planning/beads.json').read_text())
    summary=inspect(data)
    assert summary['total_beads'] >= 100
    assert summary['dependency_edges'] >= summary['total_beads']-1
    assert summary['status']['complete']>=40
    assert summary['status']['planned']>=20

def test_backlog_detects_invalid_predecessor():
    import pytest
    with pytest.raises(ValueError,match='unknown predecessor'):
        inspect({'nodes':[{'id':'bad','status':'complete','depends_on':['missing'],'acceptance':'a'}]})

def test_backlog_detects_cycle():
    import pytest
    with pytest.raises(ValueError,match='cycle'):
        inspect({'nodes':[
            {'id':'a','status':'complete','depends_on':['b'],'acceptance':'a'},
            {'id':'b','status':'complete','depends_on':['a'],'acceptance':'b'}]})
