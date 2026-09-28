#include "gateway_discovery.h"

#include <array>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstring>

#include "esp_check.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_random.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include "psa/crypto.h"
#include "sdkconfig.h"

namespace {

constexpr char kTag[] = "inkmate.discovery";
constexpr std::uint16_t kDiscoveryPort = 37653;
constexpr int kReceiveTimeoutMs = 3'000;
constexpr std::size_t kNonceBytes = 16;
constexpr std::size_t kNonceHexBytes = kNonceBytes * 2;
constexpr std::size_t kSignatureHexBytes = 64;

bool has_private_enrollment() {
    return std::strlen(CONFIG_INKMATE_GATEWAY_DEVICE_ID) > 0 &&
           std::strlen(CONFIG_INKMATE_GATEWAY_DEVICE_SECRET) >= 32;
}

void hex_encode(const std::uint8_t* input, std::size_t input_size, char* output) {
    constexpr char digits[] = "0123456789abcdef";
    for (std::size_t index = 0; index < input_size; ++index) {
        output[index * 2] = digits[input[index] >> 4];
        output[index * 2 + 1] = digits[input[index] & 0x0F];
    }
    output[input_size * 2] = '\0';
}

bool constant_time_equal(const char* left, const char* right, std::size_t size) {
    unsigned char difference = 0;
    for (std::size_t index = 0; index < size; ++index) difference |= left[index] ^ right[index];
    return difference == 0;
}

esp_err_t sign_discovery(const char* nonce, const char* url, const char* timestamp, char* output) {
    std::array<std::uint8_t, 32> digest{};
    char canonical[256]{};
    const int written = std::snprintf(canonical, sizeof(canonical), "DISCOVER\n%s\n%s\n%s", nonce, url, timestamp);
    if (written < 0 || static_cast<std::size_t>(written) >= sizeof(canonical)) return ESP_ERR_INVALID_SIZE;
    if (psa_crypto_init() != PSA_SUCCESS) return ESP_FAIL;
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, PSA_KEY_TYPE_HMAC);
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_SIGN_MESSAGE);
    psa_set_key_algorithm(&attributes, PSA_ALG_HMAC(PSA_ALG_SHA_256));
    psa_key_id_t key_id = 0;
    const psa_status_t import_result = psa_import_key(
        &attributes, reinterpret_cast<const std::uint8_t*>(CONFIG_INKMATE_GATEWAY_DEVICE_SECRET),
        std::strlen(CONFIG_INKMATE_GATEWAY_DEVICE_SECRET), &key_id);
    psa_reset_key_attributes(&attributes);
    if (import_result != PSA_SUCCESS) return ESP_FAIL;
    std::size_t digest_size = 0;
    const psa_status_t sign_result = psa_mac_compute(
        key_id, PSA_ALG_HMAC(PSA_ALG_SHA_256), reinterpret_cast<const std::uint8_t*>(canonical),
        static_cast<std::size_t>(written), digest.data(), digest.size(), &digest_size);
    psa_destroy_key(key_id);
    if (sign_result != PSA_SUCCESS || digest_size != digest.size()) {
        return ESP_FAIL;
    }
    hex_encode(digest.data(), digest.size(), output);
    return ESP_OK;
}

bool valid_url(const char* url) {
    if (std::strncmp(url, "http://", 7) != 0) return false;
    const std::size_t length = std::strlen(url);
    if (length <= 7 || length >= 128) return false;
    for (std::size_t index = 7; index < length; ++index) {
        const unsigned char character = static_cast<unsigned char>(url[index]);
        if (!(std::isalnum(character) || character == '.' || character == ':' || character == '-')) return false;
    }
    return true;
}

bool parse_unix_timestamp(const char* value, std::int64_t* output) {
    const std::size_t length = std::strlen(value);
    if (length == 0 || length > 10) return false;
    std::int64_t timestamp = 0;
    for (std::size_t index = 0; index < length; ++index) {
        if (!std::isdigit(static_cast<unsigned char>(value[index]))) return false;
        timestamp = timestamp * 10 + (value[index] - '0');
    }
    if (timestamp < 1'700'000'000 || timestamp > 4'102'444'800) return false;
    *output = timestamp;
    return true;
}

}  // namespace

namespace inkmate {

esp_err_t discover_gateway(GatewayEndpoint* endpoint) {
    if (endpoint == nullptr) return ESP_ERR_INVALID_ARG;
    endpoint->url[0] = '\0';
    endpoint->unix_timestamp = 0;
    if (!has_private_enrollment()) {
        ESP_LOGW(kTag, "gateway enrollment is not configured");
        return ESP_ERR_INVALID_STATE;
    }

    std::array<std::uint8_t, kNonceBytes> nonce_bytes{};
    char nonce[kNonceHexBytes + 1]{};
    esp_fill_random(nonce_bytes.data(), nonce_bytes.size());
    hex_encode(nonce_bytes.data(), nonce_bytes.size(), nonce);

    char request[128]{};
    const int request_size = std::snprintf(request, sizeof(request), "INKMATE/1 DISCOVER %s %s",
                                           CONFIG_INKMATE_GATEWAY_DEVICE_ID, nonce);
    if (request_size < 0 || static_cast<std::size_t>(request_size) >= sizeof(request)) return ESP_ERR_INVALID_SIZE;

    const int socket_fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (socket_fd < 0) return ESP_FAIL;
    int broadcast = 1;
    setsockopt(socket_fd, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast));
    timeval timeout{.tv_sec = kReceiveTimeoutMs / 1'000, .tv_usec = (kReceiveTimeoutMs % 1'000) * 1'000};
    setsockopt(socket_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    sockaddr_in target{};
    target.sin_family = AF_INET;
    target.sin_port = htons(kDiscoveryPort);
    esp_netif_ip_info_t ip_info{};
    esp_netif_t* station = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (station == nullptr || esp_netif_get_ip_info(station, &ip_info) != ESP_OK) {
        close(socket_fd);
        return ESP_ERR_INVALID_STATE;
    }
    target.sin_addr.s_addr = ip_info.ip.addr | ~ip_info.netmask.addr;
    if (sendto(socket_fd, request, request_size, 0, reinterpret_cast<sockaddr*>(&target), sizeof(target)) < 0) {
        close(socket_fd);
        return ESP_FAIL;
    }

    char response[256]{};
    const int received = recvfrom(socket_fd, response, sizeof(response) - 1, 0, nullptr, nullptr);
    close(socket_fd);
    if (received <= 0) return ESP_ERR_TIMEOUT;
    response[received] = '\0';

    char received_nonce[kNonceHexBytes + 1]{};
    char url[128]{};
    char timestamp[16]{};
    char signature[kSignatureHexBytes + 1]{};
    if (std::sscanf(response, "INKMATE/1 GATEWAY %32s %127s %15s %64s", received_nonce, url, timestamp, signature) != 4 ||
        !constant_time_equal(nonce, received_nonce, kNonceHexBytes) || !valid_url(url) ||
        std::strlen(signature) != kSignatureHexBytes) {
        return ESP_ERR_INVALID_RESPONSE;
    }
    std::int64_t unix_timestamp = 0;
    if (!parse_unix_timestamp(timestamp, &unix_timestamp)) return ESP_ERR_INVALID_RESPONSE;
    char expected[kSignatureHexBytes + 1]{};
    ESP_RETURN_ON_ERROR(sign_discovery(nonce, url, timestamp, expected), kTag, "sign discovery response");
    if (!constant_time_equal(signature, expected, kSignatureHexBytes)) return ESP_ERR_INVALID_CRC;
    std::strcpy(endpoint->url, url);
    endpoint->unix_timestamp = unix_timestamp;
    ESP_LOGI(kTag, "authenticated gateway discovered");
    return ESP_OK;
}

}  // namespace inkmate
