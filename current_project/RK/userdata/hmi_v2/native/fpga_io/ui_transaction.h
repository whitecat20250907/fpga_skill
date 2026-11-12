#ifndef HMI_UI_TRANSACTION_H
#define HMI_UI_TRANSACTION_H
#include "twb_core.h"
int hmi_ui_submit(struct twb_session *,const uint8_t *,size_t,int,const uint32_t *);
#endif
