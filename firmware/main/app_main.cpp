#include "board.h"
#include "provisioning.h"

#include "esp_check.h"
#include "esp_err.h"
#include "esp_log.h"
#include "inkmate_state.h"
#include "nvs_flash.h"

namespace {
constexpr char kTag[] = "inkmate";

esp_err_t initialize_nvs() {
    esp_err_t result = nvs_flash_init();
    if (result == ESP_ERR_NVS_NO_FREE_PAGES || result == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_RETURN_ON_ERROR(nvs_flash_erase(), kTag, "erase incompatible NVS");
        result = nvs_flash_init();
    }
    return result;
}
}  // namespace

extern "C" void app_main() {
    ESP_ERROR_CHECK(initialize_nvs());
    const inkmate::BootReport report = inkmate::initialize_board_safely();

    inkmate::AppState state;
    inkmate::ProvisioningManager provisioning;
    ESP_ERROR_CHECK(provisioning.initialize());
    ESP_ERROR_CHECK(provisioning.start_if_needed());
    state.set_online(provisioning.provisioned());

    ESP_LOGI(kTag, "InkMate protocol=%u mode=%u", inkmate::kProtocolVersion,
             static_cast<unsigned>(state.mode()));
    ESP_LOGI(kTag, "automatic deep sleep: %s; OTA reboot: %s",
             inkmate::automatic_deep_sleep_allowed() ? "enabled" : "blocked",
             inkmate::ota_reboot_allowed() ? "enabled" : "blocked");
    if (!report.pins_verified) {
        ESP_LOGW(kTag, "Bring-up mode only. Verify board GPIOs before enabling peripherals.");
    }
}
