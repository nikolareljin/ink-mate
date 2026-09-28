#pragma once

#include "board.h"

namespace inkmate {

// V2 only. Audio is kept in PSRAM and discarded after the bounded local capture.
esp_err_t start_audio_capture(AppState* state, const BootReport& report);
void stop_audio_capture();

}  // namespace inkmate
