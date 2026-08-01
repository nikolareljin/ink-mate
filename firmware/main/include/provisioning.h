#pragma once

#include "esp_err.h"

namespace inkmate {

class ProvisioningManager {
public:
    esp_err_t initialize();
    esp_err_t start_if_needed();
    bool provisioned() const { return provisioned_; }

private:
    bool provisioned_{false};
};

}  // namespace inkmate
