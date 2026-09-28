#pragma once

#include <cstddef>
#include <cstdint>

#include "esp_err.h"

namespace inkmate {

struct GatewayCard {
    char title[33];
    char body[241];
};

// Discovers an enrolled gateway and submits one bounded WAV request.
esp_err_t submit_wav_to_gateway(const std::uint8_t* wav, std::size_t wav_size, GatewayCard* card);

}  // namespace inkmate
