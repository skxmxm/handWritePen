#pragma once
#include <stdint.h>
extern uint32_t clockMs;
inline int64_t esp_timer_get_time(){return int64_t(clockMs)*1000;}
