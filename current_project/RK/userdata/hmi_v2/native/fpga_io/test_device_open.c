/* Driver-contract test, no device access. */
#define _GNU_SOURCE
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
static mode_t test_mode;static int calls,observed;
static int mock_stat(const char *path,struct stat *st){(void)path;st->st_mode=test_mode;return 0;}
static int mock_open(const char *path,int flags){(void)path;calls++;observed=flags;return 17;}
#define lstat mock_stat
#define open mock_open
#include "device_open.h"
int main(void){
 test_mode=S_IFREG;assert(owner_open_model_dma("ordinary-file")==-1&&calls==0);
 test_mode=S_IFLNK;assert(owner_open_model_dma("symlink")==-1&&calls==0);
 test_mode=S_IFCHR;assert(owner_open_model_dma("model-channel")==17&&calls==1);
 assert((observed&O_TRUNC)!=0&&(observed&O_NOFOLLOW)!=0&&(observed&O_CLOEXEC)!=0);
 puts("PASS: character-device-only, atomic EOP-mode open; no real hardware I/O");return 0;
}
