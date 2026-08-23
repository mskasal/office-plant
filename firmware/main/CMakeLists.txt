if(NOT DEFINED NODE_IS_ROOT)
    set(NODE_IS_ROOT 0)
endif()

idf_component_register(
    SRCS "main.c" "root_main.c" "leaf_main.c" "sleep_wake.c" "moisture_sensor.c" "ieee802154_radio.c"
         "dongle_uart.c" "node_identity.c" "pairing_mode.c" "factory_reset_button.c" "node_config.c"
    INCLUDE_DIRS "."
    REQUIRES protocol mesh driver nvs_flash
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE NODE_IS_ROOT=${NODE_IS_ROOT})
