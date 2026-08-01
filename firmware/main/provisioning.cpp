#include "provisioning.h"

#include <array>
#include <cstdio>
#include <cstring>

#include "esp_check.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "sdkconfig.h"
#include "wifi_provisioning/manager.h"
#include "wifi_provisioning/scheme_ble.h"

namespace {
constexpr char kTag[] = "inkmate.prov";
std::array<char, 20> service_name{};

void derive_identity() {
    std::uint8_t mac[6]{};
    ESP_ERROR_CHECK(esp_read_mac(mac, ESP_MAC_WIFI_STA));
    std::snprintf(service_name.data(), service_name.size(), "INKMATE_%02X%02X%02X",
                  mac[3], mac[4], mac[5]);
}
}  // namespace

namespace inkmate {

esp_err_t ProvisioningManager::initialize() {
    ESP_RETURN_ON_ERROR(esp_netif_init(), kTag, "netif init");
    esp_err_t event_result = esp_event_loop_create_default();
    if (event_result != ESP_OK && event_result != ESP_ERR_INVALID_STATE) return event_result;
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t wifi_config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&wifi_config), kTag, "wifi init");
    derive_identity();

    wifi_prov_mgr_config_t config{
        .scheme = wifi_prov_scheme_ble,
        .scheme_event_handler = WIFI_PROV_SCHEME_BLE_EVENT_HANDLER_FREE_BTDM,
    };
    ESP_RETURN_ON_ERROR(wifi_prov_mgr_init(config), kTag, "provisioning manager init");
    ESP_RETURN_ON_ERROR(wifi_prov_mgr_is_provisioned(&provisioned_), kTag, "credential check");
    return ESP_OK;
}

esp_err_t ProvisioningManager::start_if_needed() {
    if (provisioned_) {
        ESP_LOGI(kTag, "Wi-Fi credentials present; starting station");
        return esp_wifi_start();
    }
    constexpr char provisioning_pop[] = CONFIG_INKMATE_PROVISIONING_POP;
    if (std::strlen(provisioning_pop) < 16) {
        ESP_LOGE(kTag, "Provisioning disabled: configure a private per-device PoP");
        return ESP_ERR_INVALID_STATE;
    }
    ESP_LOGI(kTag, "Starting authenticated BLE provisioning: service=%s",
             service_name.data());
    wifi_prov_security1_params_t security_params{
        .data = provisioning_pop,
        .len = std::strlen(provisioning_pop),
    };
    return wifi_prov_mgr_start_provisioning(WIFI_PROV_SECURITY_1, &security_params,
                                            service_name.data(), nullptr);
}

}  // namespace inkmate
