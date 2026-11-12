/* Anlogic cdev_sgdma.c selects eop_flush in sgdma_engine_claim using O_TRUNC.
 * For this character device it selects packet completion; it is not a file
 * truncation request. Reject ordinary files and symlinks before opening. */
static int owner_open_model_dma(const char *path){
 struct stat st;
 if(lstat(path,&st)<0)return -1;
 if(!S_ISCHR(st.st_mode)){errno=ENODEV;return -1;}
 return open(path,O_RDWR|O_CLOEXEC|O_NOFOLLOW|O_TRUNC);
}
