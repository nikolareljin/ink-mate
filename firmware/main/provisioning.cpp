#include "provisioning.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "esp_check.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "sdkconfig.h"
#include "network_provisioning/manager.h"
#include "network_provisioning/scheme_ble.h"

namespace {
#ifndef CONFIG_INKMATE_WIFI_SSID
#define CONFIG_INKMATE_WIFI_SSID ""
#endif
#ifndef CONFIG_INKMATE_WIFI_PASSWORD
#define CONFIG_INKMATE_WIFI_PASSWORD ""
#endif
constexpr char kTag[] = "inkmate.prov";
std::array<char, 20> service_name{};

void wifi_event_handler(void*, esp_event_base_t event_base, std::int32_t event_id, void*) {
    if (event_base != WIFI_EVENT) return;
    if (event_id == WIFI_EVENT_STA_START || event_id == WIFI_EVENT_STA_DISCONNECTED) {
        const esp_err_t result = esp_wifi_connect();
        if (result != ESP_OK) ESP_LOGW(kTag, "Wi-Fi connect request failed: %s", esp_err_to_name(result));
    }
}

void ip_event_handler(void*, esp_event_base_t, std::int32_t event_id, void*) {
    if (event_id == IP_EVENT_STA_GOT_IP) ESP_LOGI(kTag, "Wi-Fi station connected");
}

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
    ESP_RETURN_ON_ERROR(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, nullptr), kTag,
                        "Wi-Fi event handler");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, ip_event_handler, nullptr), kTag,
                        "IP event handler");
    derive_identity();

    network_prov_mgr_config_t config{};
    config.scheme = network_prov_scheme_ble;
    config.scheme_event_handler = NETWORK_PROV_SCHEME_BLE_EVENT_HANDLER_FREE_BTDM;
    ESP_RETURN_ON_ERROR(network_prov_mgr_init(config), kTag, "provisioning manager init");
    ESP_RETURN_ON_ERROR(network_prov_mgr_is_wifi_provisioned(&provisioned_), kTag, "credential check");
    ESP_LOGI(kTag, "Wi-Fi provisioning state: %s", provisioned_ ? "ready" : "required");
    return ESP_OK;
}

esp_err_t ProvisioningManager::start_if_needed() {
    if (provisioned_) {
        wifi_config_t station{};
        std::strncpy(reinterpret_cast<char*>(station.sta.ssid), CONFIG_INKMATE_WIFI_SSID, sizeof(station.sta.ssid) - 1);
        std::strncpy(reinterpret_cast<char*>(station.sta.password), CONFIG_INKMATE_WIFI_PASSWORD, sizeof(station.sta.password) - 1);
        if (station.sta.ssid[0] != '\0') ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &station), kTag, "Wi-Fi config");
        ESP_LOGI(kTag, "Wi-Fi credentials present; starting station");
        network_prov_mgr_deinit();
        return esp_wifi_start();
    }
    constexpr char provisioning_pop[] = CONFIG_INKMATE_PROVISIONING_POP;
    if (std::strlen(provisioning_pop) < 16) {
        ESP_LOGE(kTag, "Provisioning disabled: configure a private per-device PoP");
        return ESP_ERR_INVALID_STATE;
    }
    ESP_LOGI(kTag, "Starting authenticated BLE provisioning: service=%s",
             service_name.data());
    const network_prov_security1_params_t *security_params = provisioning_pop;
    return network_prov_mgr_start_provisioning(NETWORK_PROV_SECURITY_1, security_params,
                                               service_name.data(), nullptr);
}

}  // namespace inkmate
