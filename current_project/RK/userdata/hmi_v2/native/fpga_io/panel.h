/* Same four-step sequence and ABI/activity gates as dsi_drive_control_v2.c,
 * dsi_clock_control_v3.c and board_actions.py. Uses the owner's existing BAR.
 * Neither camera/PHY controls nor guessed physical addresses are written. */
static void panel_pause(unsigned ms){struct timespec t={0,(long)ms*1000000L};nanosleep(&t,NULL);}
static uint32_t panel_read(unsigned address){uint32_t value=0;owner_read(NULL,address,&value);return value;}
static int panel_step(int clock_control,int enable){
 uint32_t pads=panel_read(0xd00),clock=panel_read(0xd04);
 if(panel_read(0x5c)!=0x56442501u || (pads&~1u)!=0x44534900u ||
    (clock&~1u)!=0x44534300u || (panel_read(0xd08)>>24)!=0xd5u ||
    (panel_read(0x60)&1u) || (panel_read(0x19c)&7u))return -1;
 if(clock_control && (pads&1u) && (!enable || clock!=0x44534300u))return -1;
 uint32_t address=clock_control?0xd04u:0xd00u;
 uint32_t value=(clock_control?0x44534300u:0x44534900u)|(unsigned)enable;
 owner_write(NULL,address,value);if(panel_read(address)!=value)return -1;
 if(!clock_control)return 0;
 panel_pause(10);uint32_t previous=0;
 for(unsigned i=0;i<4;i++){
  uint32_t window=panel_read(0xd0c),status=panel_read(0xd08);
  unsigned ui=(status>>8)&255u,hs=(status>>16)&255u,flags=status&15u;
  if((status>>24)!=0xd5u || !(status&8u) || (i&&window==previous))return -1;
  if(enable?(ui<38u||ui>40u||hs<155u||hs>157u||flags!=11u):(ui||hs||flags!=12u))return -1;
  previous=window;if(i!=3)panel_pause(2);
 }
 return 0;
}
static int panel_start(void){
 /* Preserve the separate-tool startup spacing. Back-to-back MMIO passed
  * clock readback yet left the actual display stream uninitialized after
  * SRAM programming. F663 restored publication with this four-step spacing.
  * This is settling time, not a claim that the physical panel acknowledged. */
 if(panel_step(0,0))return -1;
 panel_pause(100);
 if(panel_step(1,0))return -1;
 panel_pause(100);
 if(panel_step(0,1))return -1;
 panel_pause(100);
 if(panel_step(1,1))return -1;
 panel_pause(100);
 panel_pause(600);
 fprintf(stderr,"{\"event\":\"panel_started\",\"scope\":\"register and clock activity only, optical output unverified\"}\n");
 return 0;
}
