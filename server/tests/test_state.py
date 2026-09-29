from server.pitchstate.state import GameState

def make_frame(t,ball=True,valid=True,team='home'):
    return {'time':t,'players':[{'id':1,'team':team,'x':40+t,'y':50,'confidence':.9,'teamConfidence':.9,'role':'player'}],'ball':{'x':41+t,'y':50,'status':'observed','confidence':.8} if ball else None,'calibration':{'valid':valid,'shot':0}}

def test_possession_hysteresis_missing_evidence_and_causality():
    state=GameState()
    assert state.update(make_frame(0))['possession']=='unknown'
    assert state.update(make_frame(.2))['possession']=='unknown'
    assert state.update(make_frame(.4))['possession']=='home'
    assert state.update(make_frame(1.2,ball=False))['possession']=='unknown'
    assert all(f['time']<=1.2 for f in state.history)

def test_invalid_calibration_suppresses_tactical_geometry():
    state=GameState()
    for i in range(10):state.update(make_frame(i*.2,valid=False))
    assert not state.events
    assert state.history[-1]['state']['phase']=='insufficient_evidence'
    assert state.history[-1]['players'][0]['speedMps'] is None
