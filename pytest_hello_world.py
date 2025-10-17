#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>   // Necessário para time() usado com srand()

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_log.h"

#define PREFIX "{Rodrigo-RM:87421} "


#define QUEUE_LENGTH         8
#define QUEUE_ITEM_SIZE      sizeof(int)
#define GENERATOR_DELAY_MS   200
#define RECV_WAIT_MS         2000
#define SUPERVISOR_PERIOD_MS 3000
#define WDT_TIMEOUT_S        5

#define BIT_GEN_ALIVE        (1 << 0)
#define BIT_RECV_ALIVE       (1 << 1)
#define BIT_SUPERV_ALIVE     (1 << 2)
#define BIT_RECV_ERROR       (1 << 3)
#define BIT_QUEUE_FULL       (1 << 4)

static QueueHandle_t data_queue = NULL;
static EventGroupHandle_t sys_flags = NULL;

static void generator_task(void *arg)
{
    esp_task_wdt_add(NULL);
    int counter = 0;

    for (;;) {
        xEventGroupSetBits(sys_flags, BIT_GEN_ALIVE);

        // Usando valor aleatório (exemplo com rand), ou use counter fixo se preferir
        int value = rand() % 1000;  // Número aleatório entre 0 e 999

        BaseType_t r = xQueueSendToBack(data_queue, &value, 0);
        if (r == pdTRUE) {
            printf(PREFIX "[FILA] Dado enviado com sucesso! Valor: %d\n", value);
            xEventGroupClearBits(sys_flags, BIT_QUEUE_FULL);
        } else {
            printf(PREFIX "[FILA] FILA CHEIA! Dado descartado: %d\n", value);
            xEventGroupSetBits(sys_flags, BIT_QUEUE_FULL);
        }

        counter++;
        esp_task_wdt_reset();
        vTaskDelay(pdMS_TO_TICKS(GENERATOR_DELAY_MS));
    }
}

static void receiver_task(void *arg)
{
    esp_task_wdt_add(NULL);

    int consecutive_timeouts = 0;
    const int timeout_warning_threshold = 1;
    const int timeout_recovery_threshold = 2;
    const int timeout_fatal_threshold = 3;

    for (;;) {
        xEventGroupSetBits(sys_flags, BIT_RECV_ALIVE);

        int *pval = (int *) malloc(sizeof(int));
        if (pval == NULL) {
            printf(PREFIX "[RECV] ERRO: malloc retornou NULL. Tentando recuperar...\n");
            xEventGroupSetBits(sys_flags, BIT_RECV_ERROR);
            vTaskDelay(pdMS_TO_TICKS(500));
            esp_task_wdt_reset();
            continue;
        }

        BaseType_t got = xQueueReceive(data_queue, pval, pdMS_TO_TICKS(RECV_WAIT_MS));
        if (got == pdTRUE) {
            printf(PREFIX "[RECV] Dado recebido e transmitido: %d\n", *pval);
            free(pval);
            consecutive_timeouts = 0;
            xEventGroupClearBits(sys_flags, BIT_RECV_ERROR);
        } else {
            printf(PREFIX "[RECV] TIMEOUT: nenhum dado recebido em %d ms\n", RECV_WAIT_MS);
            consecutive_timeouts++;
            xEventGroupSetBits(sys_flags, BIT_RECV_ERROR);

            if (consecutive_timeouts >= timeout_warning_threshold) {
                printf(PREFIX "[RECV] Advertência: 1º timeout detectado (contagem=%d).\n", consecutive_timeouts);
            }

            if (consecutive_timeouts >= timeout_recovery_threshold) {
                printf(PREFIX "[RECV] Tentando recuperar: limpando fila e sinalizando gerador...\n");
                xQueueReset(data_queue);
                xEventGroupClearBits(sys_flags, BIT_QUEUE_FULL);
                vTaskDelay(pdMS_TO_TICKS(500));
            }

            if (consecutive_timeouts >= timeout_fatal_threshold) {
                printf(PREFIX "[RECV] FALHA CRÍTICA: múltiplos timeouts (%d). Reiniciando sistema!\n", consecutive_timeouts);
                free(pval);
                esp_restart();
            }

            free(pval);
        }

        esp_task_wdt_reset();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

static void supervisor_task(void *arg)
{
    esp_task_wdt_add(NULL);

    for (;;) {
        xEventGroupSetBits(sys_flags, BIT_SUPERV_ALIVE);

        EventBits_t bits = xEventGroupGetBits(sys_flags);

        printf(PREFIX "[SUPERVISOR] Status: GEN=%s | RECV=%s | SUPERV=%s | QUEUE_FULL=%s | RECV_ERR=%s\n",
            (bits & BIT_GEN_ALIVE) ? "OK" : "DOWN",
            (bits & BIT_RECV_ALIVE) ? "OK" : "DOWN",
            (bits & BIT_SUPERV_ALIVE) ? "OK" : "DOWN",
            (bits & BIT_QUEUE_FULL) ? "SIM" : "NAO",
            (bits & BIT_RECV_ERROR) ? "SIM" : "NAO"
        );

        xEventGroupClearBits(sys_flags, BIT_GEN_ALIVE | BIT_RECV_ALIVE | BIT_SUPERV_ALIVE);
        esp_task_wdt_reset();
        vTaskDelay(pdMS_TO_TICKS(SUPERVISOR_PERIOD_MS));
    }
}

void app_main(void)
{
    printf(PREFIX "[BOOT] Inicializando sistema...\n");

    // Inicializa gerador de números aleatórios
    srand((unsigned) time(NULL));

    data_queue = xQueueCreate(QUEUE_LENGTH, QUEUE_ITEM_SIZE);
    if (data_queue == NULL) {
        printf(PREFIX "[BOOT] ERRO: não foi possível criar a fila.\n");
        return;
    }

    sys_flags = xEventGroupCreate();
    if (sys_flags == NULL) {
        printf(PREFIX "[BOOT] ERRO: não foi possível criar EventGroup.\n");
        return;
    }

    // Inicializa watchdog timer com timeout em milissegundos
    esp_task_wdt_config_t wdt_config = {
        .timeout_ms = WDT_TIMEOUT_S * 1000,
        .trigger_panic = true
    };

    esp_err_t err = esp_task_wdt_init(&wdt_config);
    if (err == ESP_OK) {
        printf(PREFIX "[WDT] Watchdog inicializado (%d s).\n", WDT_TIMEOUT_S);
    } else if (err == ESP_ERR_INVALID_STATE) {
        printf(PREFIX "[WDT] Watchdog já estava inicializado.\n");
    } else {
        printf(PREFIX "[WDT] Erro na inicialização do WDT: 0x%x\n", err);
    }

    BaseType_t r;

    r = xTaskCreate(generator_task, "generator_task", 4096, NULL, 5, NULL);
    if (r != pdPASS) {
        printf(PREFIX "[BOOT] ERRO: falha ao criar generator_task\n");
    } else {
        printf(PREFIX "[BOOT] generator_task criado.\n");
    }

    r = xTaskCreate(receiver_task, "receiver_task", 4096, NULL, 5, NULL);
    if (r != pdPASS) {
        printf(PREFIX "[BOOT] ERRO: falha ao criar receiver_task\n");
    } else {
        printf(PREFIX "[BOOT] receiver_task criado.\n");
    }

    r = xTaskCreate(supervisor_task, "supervisor_task", 4096, NULL, 4, NULL);
    if (r != pdPASS) {
        printf(PREFIX "[BOOT] ERRO: falha ao criar supervisor_task\n");
    } else {
        printf(PREFIX "[BOOT] supervisor_task criado.\n");
    }

    printf(PREFIX "[BOOT] Sistema pronto. Mensagens aparecerão no terminal.\n");
}
