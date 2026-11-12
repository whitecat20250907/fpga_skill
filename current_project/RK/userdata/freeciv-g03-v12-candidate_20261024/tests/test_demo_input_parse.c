/* Exercise the actual C parser against sequence poisoning and malformed input. */
#include <assert.h>
#include "demo_input_parse.h"
int main(void)
{
  guint64 seq=0;char action[24];
  assert(demo_parse_event("event 1 wake",&seq,action) && seq==1 && !strcmp(action,"wake"));
  assert(demo_parse_event("event 18446744073709551615 end",&seq,action) && seq==G_MAXUINT64);
  const char *bad[]={"event -1 wake","event +2 wake","event 0 wake",
    "event 18446744073709551616 wake","event 999999999999999999999999999999 wake",
    "event 22 unknown","event 2 confirm extra","event 1.5 next","event 2",
    "event 2w wake","gaze .5 .5", "event 2 wakeevent 3 end","event2 wake"};
  for(size_t i=0;i<G_N_ELEMENTS(bad);i++) {
    seq=123;assert(!demo_parse_event(bad[i],&seq,action));assert(seq==123);
  }
  puts("C_EVENT_PARSER_PASS: signed/overflow/unknown/trailing inputs cannot poison sequence");
  return 0;
}
