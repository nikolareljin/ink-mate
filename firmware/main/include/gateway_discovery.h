#pragma once

#include <cstdint>

#include "esp_err.h"

namespace inkmate {

struct GatewayEndpoint {
    char url[128];
    std::int64_t unix_timestamp;
};

// Resolves an enrolled gateway at runtime. The endpoint is never persisted.
esp_err_t discover_gateway(GatewayEndpoint* endpoint);

}  // namespace inkmate
