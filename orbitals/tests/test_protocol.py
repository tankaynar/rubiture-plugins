"""main.py as Rubiture runs it: tools and commands place orbitals; actions edit them."""

import json
import subprocess
import sys

from conftest import ROOT, FakeRubiture, orbital_image

import main
from orbitals import drawing, model
from orbitals.rpc import Host


def run(rubiture, *requests):
    queue = [json.dumps(request) for request in requests]

    def readline():
        if rubiture.pending():
            return rubiture.readline()
        return queue.pop(0) + '\n' if queue else ''
    main.serve(Host(readline, rubiture.write))
    return rubiture


def invoke(contribution, kind='action', images=('orbital-1',), gesture=None):
    params = {'contributionId': contribution, 'kind': kind, 'context': {'images': list(images)}}
    if gesture is not None:
        params['gesture'] = gesture
    return {'jsonrpc': '2.0', 'id': 5, 'method': 'invoke', 'params': params}


def final(rubiture):
    return [reply for reply in rubiture.replies if reply.get('id') == 5][-1]


def test_initialize_names_the_plugin():
    rubiture = run(FakeRubiture(), {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
    assert rubiture.replies[0]['result']['name'] == 'Orbitals'


def test_a_click_on_an_atom_puts_the_orbital_on_it_upright():
    gesture = {'cancelled': False, 'kind': 'vector', 'start': {'x': 5, 'y': 6}, 'end': {'x': 5, 'y': 6},
               'length': 0, 'angleDegrees': 0, 'startAtom': {'id': 'a1', 'x': 50, 'y': 60}}
    rubiture = run(FakeRubiture(), invoke('tool-p', kind='tool', images=(), gesture=gesture))
    [added] = rubiture.calls('scene:add-image')
    payload = added['payload']
    assert (payload['x'], payload['y']) == (50, 60)
    assert payload['locks'] == ['replace', 'crop', 'rotate']
    assert model.load(payload['pluginData'])['angle'] == -90
    assert final(rubiture)['result']['ok'] is True


def test_a_drag_aims_the_orbital():
    gesture = {'cancelled': False, 'kind': 'vector', 'start': {'x': 0, 'y': 0}, 'end': {'x': 0, 'y': 40},
               'length': 40, 'angleDegrees': 90}
    rubiture = run(FakeRubiture(), invoke('tool-sp3', kind='tool', images=(), gesture=gesture))
    [added] = rubiture.calls('scene:add-image')
    assert model.load(added['payload']['pluginData'])['angle'] == 90


def test_a_place_command_asks_for_a_clickable_gesture_with_a_preview():
    answers = {'gesture': {'cancelled': True, 'reason': 'escape'}}
    rubiture = run(FakeRubiture(answers), invoke('place-dz2', kind='command', images=()))
    [asked] = rubiture.calls('gesture')
    assert asked['kind'] == 'vector' and asked['click'] is True
    assert asked['preview']['ops'][0]['origin'] == 'start'
    assert rubiture.calls('scene:add-image') == []


def test_an_action_without_an_orbital_says_so():
    rubiture = run(FakeRubiture(), invoke('flip-phase', images=()))
    assert final(rubiture)['result'] == {'ok': False, 'error': 'Select one orbital first.'}


def test_rotate_keeps_the_size_the_user_gave_it():
    orbital = model.new_orbital('p')
    image = orbital_image(orbital, height=drawing.drawing(orbital)['height'] * 2)
    rubiture = run(FakeRubiture({'scene:get-image': image}), invoke('rotate-90'))
    [updated] = rubiture.calls('scene:update-image')
    payload = updated['payload']
    turned = model.load(payload['pluginData'])
    assert turned['angle'] == 0
    assert payload['height'] == drawing.drawing(turned)['height'] * 2


def test_edit_serves_the_dialog_then_saves_once():
    events = [{'jsonrpc': '2.0', 'id': 90, 'method': 'dialogEvent',
               'params': {'event': {'type': 'change', 'field': 'type', 'value': 'sp2'}}}]
    answers = {'scene:get-image': orbital_image(), 'dialog': {'cancelled': False, 'values': {}}}
    rubiture = run(FakeRubiture(answers, inbound={'dialog': events}), invoke('edit'))
    [reply] = [r for r in rubiture.replies if r.get('id') == 90]
    assert 'picture' in reply['result']
    [updated] = rubiture.calls('scene:update-image')
    assert model.load(updated['payload']['pluginData'])['type'] == 'sp2'


def test_a_cancelled_edit_changes_nothing():
    answers = {'scene:get-image': orbital_image(), 'dialog': {'cancelled': True, 'reason': 'escape'}}
    rubiture = run(FakeRubiture(answers), invoke('edit'))
    assert rubiture.calls('scene:update-image') == []


def test_runs_as_a_process():
    process = subprocess.run([sys.executable, 'main.py'], cwd=ROOT, capture_output=True, text=True, timeout=30,
                             input=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}) + '\n')
    assert json.loads(process.stdout.splitlines()[0])['result']['name'] == 'Orbitals'
