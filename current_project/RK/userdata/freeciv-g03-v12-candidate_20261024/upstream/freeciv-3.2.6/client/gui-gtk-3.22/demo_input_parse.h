/* Strict optional-demo event parser. GPL-2.0-or-later. */
#ifndef FREECIV_DEMO_INPUT_PARSE_H
#define FREECIV_DEMO_INPUT_PARSE_H
#include <errno.h>
#include <glib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>

static gboolean demo_parse_gaze2(const char *buf,gint64 now,gint64 *stamp,double *x,double *y)
{
  char digits[24],extra;
  if(sscanf(buf,"gaze2 %23s %lf %lf %c",digits,x,y,&extra)!=3) return FALSE;
  size_t n=strlen(digits);
  if(!n || n>19) return FALSE;
  for(size_t i=0;i<n;i++) if(digits[i]<'0'||digits[i]>'9') return FALSE;
  errno=0;guint64 value=g_ascii_strtoull(digits,NULL,10);
  if(errno==ERANGE || !value || value>(guint64)now || (guint64)now-value>250000) return FALSE;
  if(!isfinite(*x)||!isfinite(*y)||*x<0||*x>1||*y<0||*y>1) return FALSE;
  *stamp=(gint64)value;return TRUE;
}

static gboolean demo_parse_event(const char *buf,guint64 *sequence,char action[24])
{
  char digits[32],extra;
  if(strncmp(buf,"event ",6)) return FALSE;
  if(sscanf(buf,"event %31s %23s %c",digits,action,&extra)!=2) return FALSE;
  size_t count=strlen(digits);
  if(!count || count>20) return FALSE;
  for(size_t i=0;i<count;i++) if(digits[i]<'0' || digits[i]>'9') return FALSE;
  errno=0;
  guint64 value=g_ascii_strtoull(digits,NULL,10);
  if(errno==ERANGE || !value) return FALSE;
  if(strcmp(action,"wake") && strcmp(action,"confirm") && strcmp(action,"cancel") &&
     strcmp(action,"next") && strcmp(action,"end") && strcmp(action,"mouse")) return FALSE;
  *sequence=value;
  return TRUE;
}
#endif
