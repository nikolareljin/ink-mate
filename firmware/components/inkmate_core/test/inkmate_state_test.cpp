#include <cassert>

#include "inkmate_state.h"

using namespace inkmate;

int main() {
    AppState app;
    app.set_online(true);
    assert(app.mode() == AppMode::Idle);
    assert(app.handle(ButtonEvent::Pressed, 10) == Intent::BeginRecording);
    assert(app.handle(ButtonEvent::Released, 20) == Intent::SubmitRecording);
    app.interaction_complete();
    assert(app.mode() == AppMode::Idle);

    assert(!app.propose_action({}, 100));
    PendingAction action{"req-1", "Restart service", "host/service", 200};
    assert(app.propose_action(action, 100));
    assert(app.handle(ButtonEvent::ShortPress, 150) == Intent::ConfirmAction);
    app.action_complete();

    assert(app.propose_action(action, 100));
    assert(app.handle(ButtonEvent::LongPress, 150) == Intent::CancelAction);
    assert(!app.pending_action());

    assert(app.propose_action(action, 100));
    assert(app.handle(ButtonEvent::ShortPress, 200) == Intent::CancelAction);
    assert(!app.pending_action());
    return 0;
}
