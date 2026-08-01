#pragma once

#include <cstdint>
#include <string>

namespace inkmate {

inline constexpr std::uint16_t kProtocolVersion = 1;

enum class CardKind : std::uint8_t { Home, Answer, Tools, Confirmation, Offline, Error };
enum class AppMode : std::uint8_t { Booting, Idle, Recording, Submitting, PendingAction, Offline, Fault };
enum class ButtonEvent : std::uint8_t { Pressed, Released, ShortPress, LongPress };
enum class Intent : std::uint8_t { None, BeginRecording, SubmitRecording, NextCard, ConfirmAction, CancelAction };

struct Card {
    CardKind kind{CardKind::Home};
    std::string title;
    std::string body;
    std::string detail;
    std::uint32_t revision{0};
};

struct Envelope {
    std::uint16_t protocol_version{kProtocolVersion};
    std::string request_id;
    std::string device_id;
    std::int64_t timestamp_ms{0};
    Card card;
    std::string error_code;
};

struct PendingAction {
    std::string request_id;
    std::string display_name;
    std::string target;
    std::int64_t expires_at_ms{0};
};

}  // namespace inkmate
