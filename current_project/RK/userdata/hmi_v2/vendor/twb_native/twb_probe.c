#include "twb_mmio.h"
#include <stdio.h>
int main(int argc,char **argv){
    if(argc!=1&&argc!=2)return 64;
    struct twb_probe p={0};
    int rc=twb_native_probe(argc==2?argv[1]:"/dev/ANLOGIC-PCI0_user",&p);
    printf("{\"status\":\"%s\",\"returncode\":%d,\"cap\":%u,\"abi\":%u,\"limits\":%u,\"device_status\":%u,\"readonly\":true,\"MMIO_writes\":0}\n",
           twb_error(rc),rc,p.cap,p.abi,p.limits,p.status);
    return rc==TWB_OK?0:(rc==TWB_UNSUPPORTED?3:1);
}
