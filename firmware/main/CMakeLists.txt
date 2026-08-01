idf_component_register(
    SRCS "app_main.cpp" "board.cpp" "provisioning.cpp"
    INCLUDE_DIRS "include"
    REQUIRES inkmate_core nvs_flash esp_system esp_wifi esp_event esp_netif
             wifi_provisioning bt driver esp_adc esp_psram app_update spi_flash
)
