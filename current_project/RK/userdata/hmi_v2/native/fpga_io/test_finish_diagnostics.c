#include <assert.h>
#include <errno.h>
#include "finish_diagnostics.h"
int main(void){
 assert(hmi_finish_result(ETIMEDOUT,0,0,0,0)==ETIMEDOUT);
 assert(hmi_finish_result(0,0,0,0,0)==0);
 assert(hmi_finish_result(0,EINVAL,0,0,0)==EINVAL);
 assert(hmi_finish_result(0,0,EIO,0,0)==EIO);
 assert(hmi_finish_result(0,0,0,EBADF,0)==EBADF);
 assert(hmi_finish_result(ETIMEDOUT,0,EIO,EBADF,4)==ETIMEDOUT);
 puts("PASS: receiver error and actual local cleanup errors are distinct");
 return 0;
}
