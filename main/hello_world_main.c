#include <stdio.h>
#include <inttypes.h>
#include "sdkconfig.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_system.h"

SemaphoreHandle_t XBinarySemaphore0;
SemaphoreHandle_t XBinarySemaphore1;
SemaphoreHandle_t XBinarySemaphore2;

void vTaskExample0(void *pvParameters) {
    while (1) {
        xSemaphoreTake(XBinarySemaphore0, portMAX_DELAY);
        printf("[Tarefa 1] Executou - Rodrigo\n");
        vTaskDelay(pdMS_TO_TICKS(1000));
        xSemaphoreGive(XBinarySemaphore1);
    }
}

void vTaskExample1(void *pvParameters) {
    while (1) {
        xSemaphoreTake(XBinarySemaphore1, portMAX_DELAY);
        printf("[Tarefa 2] Executou - Rodrigo\n");
        vTaskDelay(pdMS_TO_TICKS(1000));
        xSemaphoreGive(XBinarySemaphore2);
    }
}

void vTaskExample2(void *pvParameters) {
    while (1) {
        xSemaphoreTake(XBinarySemaphore2, portMAX_DELAY);
        printf("[Tarefa 3] Executou - Rodrigo\n");
        vTaskDelay(pdMS_TO_TICKS(1000));
        xSemaphoreGive(XBinarySemaphore0);
    }
}

void app_main(void) {
    XBinarySemaphore0 = xSemaphoreCreateBinary();
    XBinarySemaphore1 = xSemaphoreCreateBinary();
    XBinarySemaphore2 = xSemaphoreCreateBinary();

    xSemaphoreGive(XBinarySemaphore0);

    xTaskCreate(vTaskExample0, "Tarefa1", 2048, NULL, 1, NULL);
    xTaskCreate(vTaskExample1, "Tarefa2", 2048, NULL, 1, NULL);
    xTaskCreate(vTaskExample2, "Tarefa3", 2048, NULL, 1, NULL);
}
 