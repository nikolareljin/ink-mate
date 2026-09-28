#include "gateway_client.h"

#include <array>
#include <cstdio>
#include <cstring>

#include "cJSON.h"
#include "esp_check.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "gateway_discovery.h"
#include "psa/crypto.h"
#include "sdkconfig.h"

namespace {

constexpr char kTag[] = "inkmate.gateway";
constexpr char kPath[] = "/v1/interactions";

void hex_encode(const std::uint8_t* input, std::size_t input_size, char* output) {
    constexpr char digits[] = "0123456789abcdef";
    for (std::size_t index = 0; index < input_size; ++index) {
        output[index * 2] = digits[input[index] >> 4];
        output[index * 2 + 1] = digits[input[index] & 0x0F];
    }
    output[input_size * 2] = '\0';
}

esp_err_t hmac_sha256(const char* input, std::size_t input_size, char* output) {
    if (psa_crypto_init() != PSA_SUCCESS) return ESP_FAIL;
    psa_key_attributes_t attributes = PSA_KEY_ATTRIBUTES_INIT;
    psa_set_key_type(&attributes, PSA_KEY_TYPE_HMAC);
    psa_set_key_usage_flags(&attributes, PSA_KEY_USAGE_SIGN_MESSAGE);
    psa_set_key_algorithm(&attributes, PSA_ALG_HMAC(PSA_ALG_SHA_256));
    psa_key_id_t key_id = 0;
    const psa_status_t import_status = psa_import_key(
        &attributes, reinterpret_cast<const std::uint8_t*>(CONFIG_INKMATE_GATEWAY_DEVICE_SECRET),
        std::strlen(CONFIG_INKMATE_GATEWAY_DEVICE_SECRET), &key_id);
    psa_reset_key_attributes(&attributes);
    if (import_status != PSA_SUCCESS) return ESP_FAIL;
    std::array<std::uint8_t, 32> digest{};
    std::size_t digest_size = 0;
    const psa_status_t sign_status = psa_mac_compute(
        key_id, PSA_ALG_HMAC(PSA_ALG_SHA_256), reinterpret_cast<const std::uint8_t*>(input), input_size,
        digest.data(), digest.size(), &digest_size);
    psa_destroy_key(key_id);
    if (sign_status != PSA_SUCCESS || digest_size != digest.size()) return ESP_FAIL;
    hex_encode(digest.data(), digest.size(), output);
    return ESP_OK;
}

esp_err_t hash_body(const std::uint8_t* body, std::size_t body_size, char* output) {
    std::array<std::uint8_t, 32> digest{};
    std::size_t digest_size = 0;
    if (psa_crypto_init() != PSA_SUCCESS ||
        psa_hash_compute(PSA_ALG_SHA_256, body, body_size, digest.data(), digest.size(), &digest_size) != PSA_SUCCESS ||
        digest_size != digest.size()) {
        return ESP_FAIL;
    }
    hex_encode(digest.data(), digest.size(), output);
    return ESP_OK;
}

esp_err_t parse_card(const char* response, inkmate::GatewayCard* card) {
    cJSON* root = cJSON_Parse(response);
    if (root == nullptr) return ESP_ERR_INVALID_RESPONSE;
    const cJSON* card_json = cJSON_GetObjectItemCaseSensitive(root, "card");
    const cJSON* title = card_json == nullptr ? nullptr : cJSON_GetObjectItemCaseSensitive(card_json, "title");
    const cJSON* body = card_json == nullptr ? nullptr : cJSON_GetObjectItemCaseSensitive(card_json, "body");
    const bool valid = cJSON_IsString(title) && title->valuestring != nullptr &&
                       cJSON_IsString(body) && body->valuestring != nullptr;
    if (valid) {
        std::strncpy(card->title, title->valuestring, sizeof(card->title) - 1);
        std::strncpy(card->body, body->valuestring, sizeof(card->body) - 1);
    }
    cJSON_Delete(root);
    return valid ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

}  // namespace

namespace inkmate {

esp_err_t submit_wav_to_gateway(const std::uint8_t* wav, std::size_t wav_size, GatewayCard* card) {
    if (wav == nullptr || wav_size == 0 || card == nullptr) return ESP_ERR_INVALID_ARG;
    card->title[0] = '\0';
    card->body[0] = '\0';
    GatewayEndpoint endpoint{};
    ESP_RETURN_ON_ERROR(discover_gateway(&endpoint), kTag, "discover gateway");

    char body_hash[65]{};
    ESP_RETURN_ON_ERROR(hash_body(wav, wav_size, body_hash), kTag, "hash request body");
    const std::int64_t request_timestamp = endpoint.unix_timestamp;
    char canonical[192]{};
    const int canonical_size = std::snprintf(canonical, sizeof(canonical), "POST\n%s\n%lld\n%s", kPath,
                                             static_cast<long long>(request_timestamp), body_hash);
    if (canonical_size < 0 || static_cast<std::size_t>(canonical_size) >= sizeof(canonical)) return ESP_ERR_INVALID_SIZE;
    char signature[65]{};
    ESP_RETURN_ON_ERROR(hmac_sha256(canonical, static_cast<std::size_t>(canonical_size), signature), kTag,
                        "sign request");
    char url[160]{};
    const int url_size = std::snprintf(url, sizeof(url), "%s%s", endpoint.url, kPath);
    if (url_size < 0 || static_cast<std::size_t>(url_size) >= sizeof(url)) return ESP_ERR_INVALID_SIZE;

    esp_http_client_config_t config{};
    config.url = url;
    config.timeout_ms = 15'000;
    config.buffer_size = 1'024;
    config.buffer_size_tx = 1'024;
    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == nullptr) return ESP_ERR_NO_MEM;
    esp_http_client_set_method(client, HTTP_METHOD_POST);
    esp_http_client_set_header(client, "Content-Type", "audio/wav");
    esp_http_client_set_header(client, "X-InkMate-Device", CONFIG_INKMATE_GATEWAY_DEVICE_ID);
    char timestamp[16]{};
    std::snprintf(timestamp, sizeof(timestamp), "%lld", static_cast<long long>(request_timestamp));
    esp_http_client_set_header(client, "X-InkMate-Timestamp", timestamp);
    esp_http_client_set_header(client, "X-InkMate-Signature", signature);
    esp_err_t result = esp_http_client_open(client, static_cast<int>(wav_size));
    if (result == ESP_OK) {
        const int written = esp_http_client_write(client, reinterpret_cast<const char*>(wav), wav_size);
        if (written != static_cast<int>(wav_size)) result = ESP_FAIL;
    }
    if (result == ESP_OK) {
        const int headers = esp_http_client_fetch_headers(client);
        if (headers < 0 || esp_http_client_get_status_code(client) != 200) result = ESP_FAIL;
    }
    std::array<char, 1024> response{};
    if (result == ESP_OK) {
        const int read = esp_http_client_read_response(client, response.data(), response.size() - 1);
        if (read <= 0) result = ESP_FAIL;
        else result = parse_card(response.data(), card);
    }
    esp_http_client_close(client);
    esp_http_client_cleanup(client);
    if (result == ESP_OK) ESP_LOGI(kTag, "gateway response accepted");
    return result;
}

}  // namespace inkmate
