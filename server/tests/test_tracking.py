import numpy as np
from server.pitchstate.tracking import PlayerTracker,BallTracker
from server.pitchstate.perception import Detection

def test_tracks_survive_camera_pan_and_ids_reset_at_cuts():
    image=np.zeros((200,400,3),np.uint8)
    tracker=PlayerTracker()
    a=tracker.update(image,[Detection([50,50,70,100],.9,'player')],0)[0].id
    motion=np.array([[1,0,100],[0,1,0],[0,0,1]],float)
    b=tracker.update(image,[Detection([150,50,170,100],.9,'player')],.2,motion)[0].id
    assert a==b
    tracker.reset()
    assert tracker.update(image,[Detection([150,50,170,100],.9,'player')],.4)[0].id!=a

def test_ball_abstains_after_missing_interval():
    tracker=BallTracker();ball=Detection([10,10,15,15],.9,'ball')
    assert tracker.update([ball],0,100)['status']=='observed'
    assert tracker.update([],.2,100)['status']=='predicted'
    assert tracker.update([],1,100) is None
