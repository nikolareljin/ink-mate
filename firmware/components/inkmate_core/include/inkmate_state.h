#pragma once

#include <cstdint>
#include <optional>

#include "inkmate_types.h"

namespace inkmate {

class AppState {
public:
    AppMode mode() const { return mode_; }
    void set_online(bool online);
    void interaction_complete();
    bool propose_action(PendingAction action, std::int64_t now_ms);
    void action_complete();
    Intent handle(ButtonEvent event, std::int64_t now_ms);
    const std::optional<PendingAction>& pending_action() const { return pending_; }

private:
    bool pending_is_valid(std::int64_t now_ms) const;
    AppMode mode_{AppMode::Booting};
    bool button_down_{false};
    std::optional<PendingAction> pending_;
};

}  // namespace inkmate
