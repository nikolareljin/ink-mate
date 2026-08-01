#include "inkmate_state.h"

namespace inkmate {

void AppState::set_online(bool online) {
    if (mode_ == AppMode::Booting || mode_ == AppMode::Offline || mode_ == AppMode::Idle) {
        mode_ = online ? AppMode::Idle : AppMode::Offline;
    }
}

void AppState::interaction_complete() {
    if (mode_ == AppMode::Submitting) mode_ = AppMode::Idle;
}

bool AppState::propose_action(PendingAction action, std::int64_t now_ms) {
    if (action.request_id.empty() || action.expires_at_ms <= now_ms) return false;
    pending_ = std::move(action);
    mode_ = AppMode::PendingAction;
    return true;
}

void AppState::action_complete() {
    pending_.reset();
    mode_ = AppMode::Idle;
}

bool AppState::pending_is_valid(std::int64_t now_ms) const {
    return pending_.has_value() && now_ms < pending_->expires_at_ms;
}

Intent AppState::handle(ButtonEvent event, std::int64_t now_ms) {
    if (mode_ == AppMode::PendingAction && !pending_is_valid(now_ms)) {
        pending_.reset();
        mode_ = AppMode::Idle;
        return Intent::CancelAction;
    }
    if (event == ButtonEvent::Pressed) {
        button_down_ = true;
        if (mode_ == AppMode::Idle) {
            mode_ = AppMode::Recording;
            return Intent::BeginRecording;
        }
        return Intent::None;
    }
    if (event == ButtonEvent::Released) {
        button_down_ = false;
        if (mode_ == AppMode::Recording) {
            mode_ = AppMode::Submitting;
            return Intent::SubmitRecording;
        }
        return Intent::None;
    }
    if (event == ButtonEvent::ShortPress) {
        if (mode_ == AppMode::PendingAction) return Intent::ConfirmAction;
        if (mode_ == AppMode::Idle || mode_ == AppMode::Offline) return Intent::NextCard;
    }
    if (event == ButtonEvent::LongPress && mode_ == AppMode::PendingAction) {
        pending_.reset();
        mode_ = AppMode::Idle;
        return Intent::CancelAction;
    }
    return Intent::None;
}

}  // namespace inkmate
