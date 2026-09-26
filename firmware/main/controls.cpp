#include "board.h"

#include "board_profile.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace {

#if CONFIG_INKMATE_BOARD_V2
constexpr char kTag[] = "inkmate.controls";
constexpr TickType_t kPollInterval = pdMS_TO_TICKS(10);
constexpr TickType_t kDebounceInterval = pdMS_TO_TICKS(30);
constexpr TickType_t kBootLongPress = pdMS_TO_TICKS(700);
constexpr TickType_t kPowerOffPress = pdMS_TO_TICKS(2'000);

struct Button {
    gpio_num_t pin;
    bool stable_pressed;
    bool candidate_pressed;
    bool long_handled;
    bool armed;
    TickType_t candidate_started;
    TickType_t pressed_started;
};

struct Controls {
    inkmate::AppState* state;
    inkmate::BootReport report;
    Button boot;
    Button power;
};

bool pressed(gpio_num_t pin) { return gpio_get_level(pin) == 0; }

const char* intent_name(inkmate::Intent intent) {
    switch (intent) {
        case inkmate::Intent::BeginRecording: return "begin recording";
        case inkmate::Intent::SubmitRecording: return "submit recording";
        case inkmate::Intent::NextCard: return "next card";
        case inkmate::Intent::ConfirmAction: return "confirm action";
        case inkmate::Intent::CancelAction: return "cancel action";
        case inkmate::Intent::None: return "none";
    }
    return "unknown";
}

void dispatch(Controls* controls, inkmate::Intent intent) {
    if (intent == inkmate::Intent::None) return;
    ESP_LOGI(kTag, "BOOT: %s", intent_name(intent));
    const esp_err_t result = inkmate::render_interaction_card(intent, controls->report);
    if (result != ESP_OK) ESP_LOGW(kTag, "cannot refresh control card: %s", esp_err_to_name(result));
}

void handle_boot_press(Controls* controls, TickType_t now) {
    controls->boot.pressed_started = now;
    controls->boot.long_handled = false;
}

void handle_boot_release(Controls* controls, TickType_t now) {
    if (controls->boot.long_handled) {
        dispatch(controls, controls->state->handle(inkmate::ButtonEvent::Released, now));
    } else {
        dispatch(controls, controls->state->handle(inkmate::ButtonEvent::ShortPress, now));
    }
}

void scan_boot(Controls* controls, TickType_t now) {
    Button& button = controls->boot;
    const bool raw_pressed = pressed(button.pin);
    if (raw_pressed != button.candidate_pressed) {
        button.candidate_pressed = raw_pressed;
        button.candidate_started = now;
    }
    if (button.stable_pressed != button.candidate_pressed && now - button.candidate_started >= kDebounceInterval) {
        button.stable_pressed = button.candidate_pressed;
        if (button.stable_pressed) handle_boot_press(controls, now);
        else handle_boot_release(controls, now);
    }
    if (button.stable_pressed && !button.long_handled && now - button.pressed_started >= kBootLongPress) {
        button.long_handled = true;
        if (controls->state->mode() == inkmate::AppMode::PendingAction) {
            dispatch(controls, controls->state->handle(inkmate::ButtonEvent::LongPress, now));
        } else {
            dispatch(controls, controls->state->handle(inkmate::ButtonEvent::Pressed, now));
        }
    }
}

bool scan_power(Controls* controls, TickType_t now) {
    Button& button = controls->power;
    const bool raw_pressed = pressed(button.pin);
    if (raw_pressed != button.candidate_pressed) {
        button.candidate_pressed = raw_pressed;
        button.candidate_started = now;
    }
    if (button.stable_pressed != button.candidate_pressed && now - button.candidate_started >= kDebounceInterval) {
        button.stable_pressed = button.candidate_pressed;
        if (button.stable_pressed) {
            button.pressed_started = now;
            button.long_handled = false;
        } else {
            button.armed = true;
        }
    }
    if (button.armed && button.stable_pressed && !button.long_handled &&
        now - button.pressed_started >= kPowerOffPress) {
        button.long_handled = true;
        ESP_LOGW(kTag, "PWR hold: releasing battery power latch");
        gpio_set_level(inkmate::board::kPins.power_hold, 0);
        return true;
    }
    return false;
}

void controls_task(void* argument) {
    auto* controls = static_cast<Controls*>(argument);
    for (;;) {
        const TickType_t now = xTaskGetTickCount();
        scan_boot(controls, now);
        if (scan_power(controls, now)) break;
        vTaskDelay(kPollInterval);
    }
    vTaskDelete(nullptr);
}
#endif

}  // namespace

namespace inkmate {

esp_err_t start_controls(AppState* state, const BootReport& report) {
#if !CONFIG_INKMATE_BOARD_V2
    (void)state;
    (void)report;
    return ESP_ERR_NOT_SUPPORTED;
#else
    if (state == nullptr) return ESP_ERR_INVALID_ARG;
    const gpio_num_t boot_pin = board::kPins.boot_button;
    const gpio_num_t power_pin = board::kPins.power_button;
    gpio_config_t input{};
    input.mode = GPIO_MODE_INPUT;
    input.pin_bit_mask = (1ULL << boot_pin) | (1ULL << power_pin);
    input.pull_up_en = GPIO_PULLUP_ENABLE;
    ESP_RETURN_ON_ERROR(gpio_config(&input), kTag, "configure buttons");

    static Controls controls{
        .state = state,
        .report = report,
        .boot = {boot_pin, pressed(boot_pin), pressed(boot_pin), false, true, xTaskGetTickCount(), 0},
        .power = {power_pin, pressed(power_pin), pressed(power_pin), false, !pressed(power_pin), xTaskGetTickCount(), 0},
    };
    ESP_LOGI(kTag, "V2 controls active: BOOT=%d PWR=%d", boot_pin, power_pin);
    return xTaskCreate(controls_task, "inkmate_controls", 4 * 1024, &controls, 4, nullptr) == pdPASS
               ? ESP_OK
               : ESP_ERR_NO_MEM;
#endif
}

}  // namespace inkmate
